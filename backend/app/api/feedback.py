import asyncio
from fastapi import APIRouter, HTTPException
from app.storage.session_store import load_session, save_session
from app.core.exceptions import SessionNotFoundError
from app.core.models import InterviewState, SessionSummary, EvaluationResult, SentenceAnnotation
from app.core.dimensions import get_dimension_name
from app.llm.client import chat_completion
from app.agents.evaluator import _extract_json

router = APIRouter()

GRADE_ZH = [(90, "优秀"), (75, "良好"), (60, "一般"), (0, "待提升")]
GRADE_EN = [(90, "Excellent"), (75, "Good"), (60, "Average"), (0, "Needs Work")]


def _grade(score: float, language: str) -> str:
    table = GRADE_EN if language == "en" else GRADE_ZH
    for threshold, label in table:
        if score >= threshold:
            return label
    return table[-1][1]


def _weakest_dim(ev: EvaluationResult) -> str | None:
    if not ev.dimension_scores:
        return None
    return min(ev.dimension_scores, key=lambda d: d.score).dimension


async def _model_answer(
    question: str,
    language: str,
    dimension_focus: str | None = None,
    user_answer: str | None = None,
    overall_score: float = 5.0,
) -> str:
    if language == "zh":
        sys_msg = "你是一位面试辅导专家，擅长用真实、有说服力的方式呈现面试故事。"
        focus_hint = f"\n特别关注维度：{dimension_focus}（请在回答中用具体例子体现这一维度的亮点）。" if dimension_focus else ""
        if user_answer and overall_score >= 3:
            draft_prompt = (
                f"以下是候选人对面试题的真实回答：\n\n{user_answer}\n\n"
                f"请基于候选人的回答，输出一个改进版本（150字以内）。要求：\n"
                f"1. 保留候选人的核心事件和思路，不要换成完全不同的案例\n"
                f"2. 语言自然流畅，避免显式的'情境/任务/行动/结果'标签\n"
                f"3. 如缺乏量化数据，补充合理的虚构数字\n"
                f"4. 如有'我们'但无个人角色，改为'我负责…'\n"
                f"{focus_hint}\n\n面试题：{question}"
            )
        else:
            draft_prompt = (
                f"请为以下面试题生成一个示范回答（150字以内）。"
                f"语言自然流畅，避免显式的'情境/任务/行动/结果'标签，用真实对话的方式讲故事。{focus_hint}\n\n问题：{question}"
            )
        critique_prompt_tmpl = (
            "以下是一个面试示范回答的草稿：\n\n{draft}\n\n"
            "请从以下三个角度批判并改进它：\n"
            "1. 是否有具体的数字或量化结果？（没有则补充虚拟但合理的数据）\n"
            "2. 候选人的个人贡献是否清晰？（有'我们'但无个人角色则修正）\n"
            "3. 表达是否自然流畅？（有模板痕迹则改写）\n"
            "直接输出改进后的最终版本（150字以内），不要输出批判分析过程。"
        )
    else:
        sys_msg = "You are an expert interview coach who crafts authentic, compelling interview stories."
        focus_hint = f"\nPay special attention to dimension: {dimension_focus} (use a concrete example to highlight this dimension)." if dimension_focus else ""
        if user_answer and overall_score >= 3:
            draft_prompt = (
                f"Here is the candidate's actual answer:\n\n{user_answer}\n\n"
                f"Write an improved version (under 150 words) based on the candidate's answer. Requirements:\n"
                f"1. Keep the candidate's core story and ideas — do not substitute a completely different example\n"
                f"2. Make it natural and conversational — avoid explicit STAR labels\n"
                f"3. Add plausible quantified results if missing\n"
                f"4. Replace vague 'we' with explicit 'I was responsible for…'\n"
                f"{focus_hint}\n\nQuestion: {question}"
            )
        else:
            draft_prompt = (
                f"Write a model answer (under 150 words) for the interview question below. "
                f"Make it natural and conversational — avoid explicit 'Situation/Task/Action/Result' labels; tell it as a real story.{focus_hint}\n\nQuestion: {question}"
            )
        critique_prompt_tmpl = (
            "Here is a draft model answer:\n\n{draft}\n\n"
            "Critique and improve it on three dimensions:\n"
            "1. Does it include specific numbers or quantified results? (If not, add plausible data)\n"
            "2. Is the candidate's personal contribution clear? (Fix vague 'we' with explicit individual role)\n"
            "3. Does it sound natural and conversational? (Rewrite any template-sounding parts)\n"
            "Output only the improved final version (under 150 words). Do not show the critique."
        )

    draft = await chat_completion(
        [{"role": "system", "content": sys_msg}, {"role": "user", "content": draft_prompt}],
        temperature=0.7,
    )
    return await chat_completion(
        [{"role": "system", "content": sys_msg},
         {"role": "user", "content": critique_prompt_tmpl.format(draft=draft)}],
        temperature=0.7,
    )


async def _annotate_and_critique(
    question: str,
    answer: str,
    dimension_scores: list,
    language: str,
) -> tuple[list[dict], dict]:
    """Returns (sentence_annotations, critique dict)."""
    if not answer.strip():
        return [], {"highlights": [], "improvements": []}

    if language == "zh":
        dim_summary = "、".join(f"{ds.dimension}:{ds.score:.0f}" for ds in dimension_scores) or "无"
        sys_msg = "你是专业面试辅导专家，负责对候选人回答进行逐句标注和整体评价。"
        user_msg = (
            f"面试题：{question}\n"
            f"候选人回答：{answer}\n"
            f"维度分数参考：{dim_summary}\n\n"
            f"请完成以下两项任务，输出JSON：\n\n"
            f"任务1：逐句标注\n"
            f"将回答按语义切割成短句（尽量保留原文），对每句标注：\n"
            f'- label: "good"（亮点：有量化数据/个人角色清晰/有具体案例）\n'
            f'         "vague"（模糊：表达可以更具体）\n'
            f'         "weak"（薄弱：缺失关键要素或跑题）\n'
            f'         "ok"（普通：无需特别标注）\n'
            f"- comment: 简短评价（15字以内，ok类可留空）\n\n"
            f"任务2：整体评价\n"
            f"- highlights: 2-3条做得好的地方（每条20字以内）\n"
            f"- improvements: 2-3条需要改进的地方（每条20字以内）\n\n"
            f'输出格式：\n{{"sentence_annotations": [{{"text": "原文", "label": "good", "comment": "评价"}}], '
            f'"highlights": ["亮点1"], "improvements": ["改进1"]}}'
        )
    else:
        dim_summary = ", ".join(f"{ds.dimension}:{ds.score:.0f}" for ds in dimension_scores) or "none"
        sys_msg = "You are a professional interview coach who annotates candidate answers and provides structured feedback."
        user_msg = (
            f"Question: {question}\n"
            f"Candidate Answer: {answer}\n"
            f"Dimension scores: {dim_summary}\n\n"
            f"Complete two tasks and output JSON:\n\n"
            f"Task 1: Sentence-level annotation\n"
            f"Split the answer into semantic clauses (preserve original text as closely as possible), label each:\n"
            f'- label: "good" (strength: quantified/personal role clear/specific example)\n'
            f'         "vague" (could be more specific)\n'
            f'         "weak" (missing key element or off-topic)\n'
            f'         "ok" (neutral, no annotation needed)\n'
            f"- comment: brief note (under 15 words, empty for ok)\n\n"
            f"Task 2: Overall critique\n"
            f"- highlights: 2-3 things done well (under 20 words each)\n"
            f"- improvements: 2-3 things to improve (under 20 words each)\n\n"
            f'Output format:\n{{"sentence_annotations": [{{"text": "clause", "label": "good", "comment": "note"}}], '
            f'"highlights": ["strength 1"], "improvements": ["improvement 1"]}}'
        )

    try:
        raw = await chat_completion(
            [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            temperature=0.3,
        )
        data = _extract_json(raw)
        annotations = [
            a for a in data.get("sentence_annotations", [])
            if isinstance(a, dict) and "text" in a and "label" in a
        ]
        critique = {
            "highlights": data.get("highlights", []),
            "improvements": data.get("improvements", []),
        }
        return annotations, critique
    except Exception:
        return [], {"highlights": [], "improvements": []}


async def _ai_summary(evals: list[EvaluationResult], total_score: float, language: str) -> str:
    evals_text = "\n".join(
        f"Q{e.question_index}: {e.question_text[:80]} → {e.overall_score:.1f}/10"
        for e in evals if not e.is_probe
    )
    if language == "zh":
        prompt = f"根据以下面试评分，生成100-150字总结评语，点出3个优点和2个改进方向：\n总分：{total_score:.0f}/100\n{evals_text}"
        sys_msg = "你是面试评估专家。"
    else:
        prompt = f"Based on these scores, write a 100-150 word summary with 3 strengths and 2 improvements:\nTotal: {total_score:.0f}/100\n{evals_text}"
        sys_msg = "You are an expert interview evaluator."
    return await chat_completion(
        [{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}],
        temperature=0.5,
    )


@router.post("/sessions/{session_id}/finalize")
async def finalize_session(session_id: str, force: bool = False):
    try:
        session = await load_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.summary is not None and not force:
        return session.summary.model_dump()

    language = session.profile.language.value
    main_evals = [e for e in session.evaluations if not e.is_probe]

    # Per-dimension aggregate scores
    dim_lists: dict[str, list[float]] = {d: [] for d in session.active_dimensions}
    for ev in main_evals:
        for ds in ev.dimension_scores:
            if ds.dimension in dim_lists:
                dim_lists[ds.dimension].append(ds.score)

    radar_data = {
        d: round(sum(v) / len(v), 2) if v else 0.0
        for d, v in dim_lists.items()
    }

    total_score = round(
        sum(e.overall_score for e in main_evals) / max(len(main_evals), 1) * 10, 1
    )
    grade = _grade(total_score, language)

    # Run model answers and annotation+critique in parallel
    n = len(session.evaluations)
    all_results = await asyncio.gather(
        *[_model_answer(e.question_text, language, _weakest_dim(e), e.answer_transcript, e.overall_score)
          for e in session.evaluations],
        *[_annotate_and_critique(e.question_text, e.answer_transcript, e.dimension_scores, language)
          for e in session.evaluations],
    )
    answers = all_results[:n]
    annot_results = all_results[n:]
    for ev, ans, (annotations, critique) in zip(session.evaluations, answers, annot_results):
        ev.model_answer = ans
        ev.sentence_annotations = [SentenceAnnotation(**a) for a in annotations]
        ev.answer_critique = critique

    # Per-dimension detail
    dimension_details: dict[str, dict] = {}
    for dim in session.active_dimensions:
        scored = [
            (e, next((ds for ds in e.dimension_scores if ds.dimension == dim), None))
            for e in main_evals
        ]
        scored = [(e, ds) for e, ds in scored if ds]
        if not scored:
            continue
        best = max(scored, key=lambda x: x[1].score)
        worst = min(scored, key=lambda x: x[1].score)
        feedbacks = [ds.feedback for _, ds in scored if ds.feedback]
        dim_name = get_dimension_name(dim, language)
        suggestion = (
            f"重点提升{dim_name}，多用具体数据和案例。"
            if language == "zh"
            else f"Improve {dim_name} with more specific data and examples."
        )
        dimension_details[dim] = {
            "score": radar_data.get(dim, 0.0),
            "analysis": " ".join(feedbacks[:2]),
            "suggestions": suggestion,
            "best_question_index": best[0].question_index,
            "worst_question_index": worst[0].question_index,
        }

    ai_summary = await _ai_summary(session.evaluations, total_score, language)

    summary = SessionSummary(
        total_score=total_score,
        grade=grade,
        ai_summary=ai_summary,
        active_dimensions=session.active_dimensions,
        radar_data=radar_data,
        dimension_details=dimension_details,
        per_question=session.evaluations,
    )
    session.summary = summary
    await save_session(session)
    return summary.model_dump()


@router.get("/sessions/{session_id}/feedback")
async def get_feedback(session_id: str):
    try:
        session = await load_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.summary is None:
        raise HTTPException(status_code=404, detail="Call /finalize first")
    return session.summary.model_dump()
