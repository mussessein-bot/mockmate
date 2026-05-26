import asyncio
from fastapi import APIRouter, HTTPException
from app.storage.session_store import load_session, save_session
from app.core.exceptions import SessionNotFoundError
from app.core.models import InterviewState, SessionSummary, EvaluationResult
from app.core.dimensions import get_dimension_name
from app.llm.client import chat_completion

router = APIRouter()

GRADE_ZH = [(90, "优秀"), (75, "良好"), (60, "一般"), (0, "待提升")]
GRADE_EN = [(90, "Excellent"), (75, "Good"), (60, "Average"), (0, "Needs Work")]


def _grade(score: float, language: str) -> str:
    table = GRADE_EN if language == "en" else GRADE_ZH
    for threshold, label in table:
        if score >= threshold:
            return label
    return table[-1][1]


async def _model_answer(question: str, language: str) -> str:
    if language == "zh":
        prompt = f"请用STAR法则，为以下面试题生成一个简洁的示范回答（150字以内）：\n{question}"
        sys_msg = "你是一位面试辅导专家。"
    else:
        prompt = f"Using the STAR method, write a concise model answer (under 150 words) for:\n{question}"
        sys_msg = "You are an expert interview coach."
    return await chat_completion(
        [{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}],
        temperature=0.5,
    )


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
async def finalize_session(session_id: str):
    try:
        session = await load_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.summary is not None:
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

    # Generate model answers in parallel
    answers = await asyncio.gather(
        *[_model_answer(e.question_text, language) for e in session.evaluations]
    )
    for ev, ans in zip(session.evaluations, answers):
        ev.model_answer = ans

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
