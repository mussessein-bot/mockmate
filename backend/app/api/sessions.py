import json
from fastapi import APIRouter, HTTPException
from app.api.schemas import (
    CreateSessionRequest, CreateSessionResponse,
    AnalyzeRoleRequest, RefineAnalysisRequest, WebSearchAnalyzeRequest, JobAnalysisResponse,
)
from app.core.models import InterviewSession, CandidateProfile
from app.core.dimensions import DEFAULT_DIMENSIONS
from app.core.memory import init_profile
from app.storage.session_store import save_session, load_session, delete_session
from app.storage.database import get_db
from app.core.exceptions import SessionNotFoundError
from app.llm.client import chat_completion_json
from app.llm.prompts.analysis_prompts import build_analysis_prompt
from app.services.web_search import search_job_info

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
    }


@router.post("/analyze-role", response_model=JobAnalysisResponse)
async def analyze_role(body: AnalyzeRoleRequest):
    messages = build_analysis_prompt(
        target_role=body.target_role,
        target_company=body.target_company,
        job_description=body.job_description,
        language=body.language,
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
    )
    raw = await chat_completion_json(messages, temperature=0.3)
    return _parse_analysis(raw)


@router.post("/web-search-analyze", response_model=JobAnalysisResponse)
async def web_search_analyze(body: WebSearchAnalyzeRequest):
    search_text = await search_job_info(body.target_role, body.target_company)
    messages = build_analysis_prompt(
        target_role=body.target_role,
        target_company=body.target_company,
        job_description=body.job_description,
        language=body.language,
        extra_context=f"以下是互联网上搜索到的相关信息，供参考：\n{search_text}",
    )
    raw = await chat_completion_json(messages, temperature=0.3)
    return _parse_analysis(raw)
