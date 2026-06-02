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


def _weakest_dim(ev: EvaluationResult) -> str | None:
    if not ev.dimension_scores:
        return None
    return min(ev.dimension_scores, key=lambda d: d.score).dimension


async def _model_answer(question: str, language: str, dimension_focus: str | None = None) -> str:
    if language == "zh":
        focus_hint = f"\n特别关注维度：{dimension_focus}（请在回答中用具体例子体现这一维度的亮点）。" if dimension_focus else ""
        draft_prompt = (
            f"请为以下面试题生成一个示范回答（150字以内）。"
            f"语言自然流畅，避免显式的'情境/任务/行动/结果'标签，用真实对话的方式讲故事。{focus_hint}\n\n问题：{question}"
        )
        sys_msg = "你是一位面试辅导专家，擅长用真实、有说服力的方式呈现面试故事。"
    else:
        focus_hint = f"\nPay special attention to dimension: {dimension_focus} (use a concrete example to highlight this dimension)." if dimension_focus else ""
        draft_prompt = (
            f"Write a model answer (under 150 words) for the interview question below. "
            f"Make it natural and conversational — avoid explicit 'Situation/Task/Action/Result' labels; tell it as a real story.{focus_hint}\n\nQuestion: {question}"
        )
        sys_msg = "You are an expert interview coach who crafts authentic, compelling interview stories."

    draft = await chat_completion(
        [{"role": "system", "content": sys_msg}, {"role": "user", "content": draft_prompt}],
        temperature=0.7,
    )

    if language == "zh":
        critique_prompt = (
            f"以下是一个面试示范回答的草稿：\n\n{draft}\n\n"
            f"请从以下三个角度批判并改进它：\n"
            f"1. 是否有具体的数字或量化结果？（没有则补充虚拟但合理的数据）\n"
            f"2. 候选人的个人贡献是否清晰？（有'我们'但无个人角色则修正）\n"
            f"3. 表达是否自然流畅？（有模板痕迹则改写）\n"
            f"直接输出改进后的最终版本（150字以内），不要输出批判分析过程。"
        )
    else:
        critique_prompt = (
            f"Here is a draft model answer:\n\n{draft}\n\n"
            f"Critique and improve it on three dimensions:\n"
            f"1. Does it include specific numbers or quantified results? (If not, add plausible data)\n"
            f"2. Is the candidate's personal contribution clear? (Fix vague 'we' with explicit individual role)\n"
            f"3. Does it sound natural and conversational? (Rewrite any template-sounding parts)\n"
            f"Output only the improved final version (under 150 words). Do not show the critique."
        )

    return await chat_completion(
        [{"role": "system", "content": sys_msg}, {"role": "user", "content": critique_prompt}],
        temperature=0.7,
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

    # Generate model answers in parallel (two-round self-critique, focused on weakest dimension)
    answers = await asyncio.gather(
        *[_model_answer(e.question_text, language, _weakest_dim(e)) for e in session.evaluations]
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
