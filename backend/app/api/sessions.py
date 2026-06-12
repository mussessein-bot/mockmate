import json
from fastapi import APIRouter, HTTPException
from app.api.schemas import (
    CreateSessionRequest, CreateSessionResponse,
    AnalyzeRoleRequest, RefineAnalysisRequest, WebSearchAnalyzeRequest,
    JobAnalysisResponse, WebSearchAnalyzeResponse, ExtractedQuestion,
    MemorySnapshotResponse,
)
from app.core.models import InterviewSession, CandidateProfile
from app.core.dimensions import DEFAULT_DIMENSIONS
from app.core.memory import init_profile, normalize_profile, topic_coverage_labels
from app.storage.session_store import save_session, load_session, delete_session
from app.storage.database import get_db
from app.storage.memory_store import job_cache_key, load_job_knowledge, save_job_knowledge
from app.core.exceptions import SessionNotFoundError
from app.llm.client import chat_completion_json
from app.llm.prompts.analysis_prompts import build_analysis_prompt, build_extraction_prompt
from app.services.web_search import search_job_info, search_interview_info

router = APIRouter()


async def _parse_resume(resume_text: str) -> dict:
    """LLM-parse resume into structured JSON for interviewer personalization."""
    messages = [
        {"role": "system", "content": "你是简历解析助手，输出严格 JSON，不含其他文字。"},
        {"role": "user", "content": f"""从以下简历提取结构化信息，输出 JSON：
{{
  "main_projects": ["项目名：一句话简介"],
  "tech_stack": ["技术1", "技术2"],
  "years_of_experience": 2,
  "highlights": ["最值得深挖的经历1", "最值得深挖的经历2"],
  "potential_weak_areas": ["可能的薄弱点1"]
}}

简历：
{resume_text}"""},
    ]
    try:
        return await chat_completion_json(messages, temperature=0.2)
    except Exception:
        return {}


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(body: CreateSessionRequest):
    profile = CandidateProfile(
        name=body.name,
        target_role=body.target_role,
        target_company=body.target_company,
        job_description=body.job_description,
        resume_text=body.resume_text,
        language=body.language,
    )
    active_dims = DEFAULT_DIMENSIONS.get(body.interview_type.value, DEFAULT_DIMENSIONS["behavioral"])

    # Load historical corrections for this role (cross-session RLHF)
    historical_constraints: list[str] = []
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT tags, note FROM correction_log WHERE target_role = ? ORDER BY created_at DESC LIMIT 15",
            (body.target_role,),
        )
        rows = await cursor.fetchall()
    if rows:
        tag_counts: dict[str, int] = {}
        for row in rows:
            for tag in json.loads(row["tags"]):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        summary = "、".join(f"{tag}（{cnt}次）" for tag, cnt in tag_counts.items())
        historical_constraints.append(
            f"历史用户对「{body.target_role}」岗位面试的反馈：请避免出现以下类型的问题：{summary}"
        )

    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT tags, interview_type, persona, question_type, hit_count
            FROM correction_log
            WHERE target_role = ?
              AND (interview_type IS NULL OR interview_type = ?)
              AND (expires_at IS NULL OR expires_at > datetime('now'))
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (body.target_role, body.interview_type.value),
        )
        structured_rows = await cursor.fetchall()
    if structured_rows:
        tag_counts: dict[str, int] = {}
        question_type_counts: dict[str, int] = {}
        persona_counts: dict[str, int] = {}
        for row in structured_rows:
            weight = int(row["hit_count"] or 1)
            try:
                tags = json.loads(row["tags"])
            except Exception:
                tags = []
            for tag in tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + weight
            if row["question_type"]:
                question_type_counts[row["question_type"]] = question_type_counts.get(row["question_type"], 0) + weight
            if row["persona"]:
                persona_counts[row["persona"]] = persona_counts.get(row["persona"], 0) + weight

        details = [f"tags: {'; '.join(f'{tag}({cnt}x)' for tag, cnt in tag_counts.items())}"]
        if question_type_counts:
            details.append(
                "question types: "
                + "; ".join(f"{qt}({cnt}x)" for qt, cnt in question_type_counts.items())
            )
        if persona_counts:
            details.append(
                "personas: "
                + "; ".join(f"{persona}({cnt}x)" for persona, cnt in persona_counts.items())
            )
        historical_constraints.append(
            f"Structured correction memory for target role '{body.target_role}' "
            f"and interview type '{body.interview_type.value}'. Avoid similar questions. "
            + " | ".join(details)
        )

    resume_parsed = await _parse_resume(body.resume_text) if body.resume_text else {}

    session = InterviewSession(
        profile=profile,
        interview_type=body.interview_type,
        interview_mode=body.interview_mode,
        interview_interface=body.interview_interface,
        persona=body.persona,
        active_dimensions=active_dims,
        candidate_profile_json=init_profile(profile),
        resume_parsed=resume_parsed,
        max_questions=8 if body.interview_mode.value == "preset" else 12,
        interviewer_constraints=historical_constraints,
        job_analysis=body.job_analysis or {},
    )
    await save_session(session)
    return CreateSessionResponse(
        session_id=session.session_id,
        state=session.state,
        active_dimensions=session.active_dimensions,
        interview_interface=session.interview_interface,
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    try:
        session = await load_session(session_id)
        return session.model_dump()
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/sessions/{session_id}/memory", response_model=MemorySnapshotResponse)
async def get_session_memory(session_id: str):
    try:
        session = await load_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    profile = normalize_profile(session.candidate_profile_json)
    last_probe_reason = None
    for evaluation in reversed(session.evaluations):
        if evaluation.probe_reason:
            last_probe_reason = evaluation.probe_reason
            break

    return MemorySnapshotResponse(
        candidate_profile=profile,
        topic_coverage=profile.get("topic_coverage", []),
        topic_labels=topic_coverage_labels(profile),
        skills_mentioned=profile.get("skills_mentioned", []),
        projects=profile.get("projects", []),
        interviewer_constraints=session.interviewer_constraints,
        active_dimensions=session.active_dimensions,
        probe_count=session.probe_count,
        max_probes=2,
        last_probe_reason=last_probe_reason,
    )


@router.delete("/sessions/{session_id}")
async def delete_session_route(session_id: str):
    try:
        await delete_session(session_id)
        return {"success": True}
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


def _parse_analysis(raw: dict) -> dict:
    """Normalize LLM output to consistent JobAnalysis shape."""
    dims = raw.get("core_dimensions", [])
    return {
        "core_dimensions": [
            {
                "name": d.get("name", ""),
                "description": d.get("description", ""),
                "weight": d.get("weight", "中"),
            }
            for d in dims
        ],
        "interview_style": raw.get("interview_style", ""),
        "key_tips": raw.get("key_tips", ""),
        "summary": raw.get("summary", ""),
        "advisor_research_summary": raw.get("advisor_research_summary"),
    }


@router.post("/analyze-role", response_model=JobAnalysisResponse)
async def analyze_role(body: AnalyzeRoleRequest):
    messages = build_analysis_prompt(
        target_role=body.target_role,
        target_company=body.target_company,
        job_description=body.job_description,
        language=body.language,
        interview_type=body.interview_type,
    )
    raw = await chat_completion_json(messages, temperature=0.3)
    return _parse_analysis(raw)


@router.post("/refine-analysis", response_model=JobAnalysisResponse)
async def refine_analysis(body: RefineAnalysisRequest):
    extra_parts = [f"用户补充说明：{body.user_note}"]
    if body.with_search:
        search_text = await search_job_info(body.target_role, body.target_company)
        extra_parts.append(f"以下是互联网上搜索到的相关信息，供参考：\n{search_text}")
    messages = build_analysis_prompt(
        target_role=body.target_role,
        target_company=body.target_company,
        job_description=body.job_description,
        language=body.language,
        extra_context="\n\n".join(extra_parts),
        interview_type=body.interview_type,
    )
    raw = await chat_completion_json(messages, temperature=0.3)
    return _parse_analysis(raw)


@router.post("/web-search-analyze", response_model=WebSearchAnalyzeResponse)
async def web_search_analyze(body: WebSearchAnalyzeRequest):
    # For graduate, synthesize target_role/company from structured fields
    effective_role = body.target_role
    effective_company = body.target_company
    if body.interview_type == "graduate":
        parts = [body.target_school or "", body.target_department or ""]
        effective_company = " ".join(p for p in parts if p) or body.target_company

    cache_key = job_cache_key(
        interview_type=body.interview_type,
        target_role=effective_role,
        target_company=effective_company,
        target_school=body.target_school,
        target_department=body.target_department,
        target_advisor=body.target_advisor,
        research_direction=body.research_direction,
    )
    cached = await load_job_knowledge(cache_key)
    if cached:
        cached_questions = [
            ExtractedQuestion(**q) for q in cached.get("extracted_questions", [])
            if q.get("question")
        ]
        return WebSearchAnalyzeResponse(
            **cached["analysis"],
            extracted_questions=cached_questions,
            search_available=bool(cached.get("search_text")),
        )

    search_text = await search_interview_info(
        interview_type=body.interview_type,
        target_role=effective_role,
        target_company=effective_company,
        target_school=body.target_school,
        target_department=body.target_department,
        target_advisor=body.target_advisor,
        research_direction=body.research_direction,
    )

    search_available = bool(search_text)

    # Step 1: extract real interview questions from search results
    extracted: list[ExtractedQuestion] = []
    if search_text:
        try:
            extraction_messages = build_extraction_prompt(search_text, body.interview_type, body.language)
            raw_extraction = await chat_completion_json(extraction_messages, temperature=0.1)
            for q in raw_extraction.get("questions", []):
                if q.get("question"):
                    extracted.append(ExtractedQuestion(
                        category=q.get("category", ""),
                        question=q["question"],
                    ))
        except Exception:
            pass

    # Step 2: job analysis with search results as context
    if body.interview_type == "graduate":
        metadata = (
            f"目标学校：{body.target_school or '未填写'}\n"
            f"目标学院/专业：{body.target_department or body.target_role}\n"
            f"目标导师：{body.target_advisor or '未指定'}\n"
            f"申请/研究方向：{body.research_direction or body.target_role}\n"
        )
        extra_context = (
            "研究生招生面试结构化输入：\n"
            f"{metadata}\n"
            "请在输出的 advisor_research_summary 字段中明确写出目标导师姓名和研究方向总结；"
            "如果联网结果没有找到目标导师，也必须说明未找到，不要用学院泛化信息替代目标导师。\n"
        )
    else:
        extra_context = None
    if search_text:
        if body.interview_type == "graduate":
            extra_context += (
                "以下是联网搜索到的研究生招生相关信息，供分析时参考。请优先采信学校官网、学院官网、教师主页、课题组主页；"
                "其次参考 Google Scholar / 论文 / 学术主页；最后才参考面经内容。若搜索结果中包含目标导师或相关导师，"
                "请总结其研究方向、常用方法/技术、代表性课题，并转化为面试可能考察的能力维度与准备建议。\n"
                f"{search_text}"
            )
        else:
            extra_context = f"以下是互联网上搜索到的相关信息，供参考：\n{search_text}"

    messages = build_analysis_prompt(
        target_role=effective_role,
        target_company=effective_company,
        job_description=body.job_description,
        language=body.language,
        extra_context=extra_context,
        interview_type=body.interview_type,
    )
    raw = await chat_completion_json(messages, temperature=0.3)
    analysis = _parse_analysis(raw)

    await save_job_knowledge(
        cache_key=cache_key,
        interview_type=body.interview_type,
        target_role=effective_role,
        target_company=effective_company,
        target_school=body.target_school,
        target_department=body.target_department,
        target_advisor=body.target_advisor,
        research_direction=body.research_direction,
        search_text=search_text,
        extracted_questions=[q.model_dump() for q in extracted],
        analysis=analysis,
    )

    return WebSearchAnalyzeResponse(
        **analysis,
        extracted_questions=extracted,
        search_available=search_available,
    )
