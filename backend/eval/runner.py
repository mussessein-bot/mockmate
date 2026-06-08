from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import eval  # noqa: F401
from app.core.models import (
    CandidateProfile, InterviewSession, InterviewState, InterviewMode,
    InterviewInterface, InterviewType, Language, Message, MessageRole,
    PersonaType, EvaluationResult,
)
from app.core.memory import init_profile, merge_profile_update
from app.core.dimensions import DEFAULT_DIMENSIONS
from app.core.state_machine import (
    transition_after_answer, apply_probe, apply_question, can_probe,
)
from app.agents.strategy import StrategyAgent
from app.agents.interviewer import InterviewerAgent
from app.agents.evaluator import EvaluatorAgent
from eval.client import candidate_chat
from eval.prompts import build_candidate_messages


@dataclass
class TurnRecord:
    turn_index: int        # 1-based, counts ALL questions including probes
    question: str
    candidate_answer: str
    is_probe: bool
    state_label: str       # InterviewState value at time of question
    eval_result: EvaluationResult


@dataclass
class SessionTranscript:
    scenario_id: str
    persona: str
    job_type: str
    target_role: str
    interview_type: str
    interviewer_persona: str
    opening: str
    turns: list[TurnRecord] = field(default_factory=list)
    closing: str = ""

    def as_text(self) -> str:
        lines = [
            f"[开场白]",
            self.opening,
            "",
        ]
        for t in self.turns:
            probe_tag = "（追问）" if t.is_probe else ""
            lines.append(f"[Q{t.turn_index}{probe_tag} | {t.state_label}]")
            lines.append(f"面试官：{t.question}")
            lines.append(f"候选人：{t.candidate_answer}")
            scores = ", ".join(
                f"{s.dimension}={s.score:.1f}" for s in t.eval_result.dimension_scores
            )
            fb_parts = [s.feedback for s in t.eval_result.dimension_scores if s.feedback]
            feedback_text = " | ".join(fb_parts[:3])  # first 3 feedbacks to keep concise
            lines.append(f"[系统评分] 总分={t.eval_result.overall_score:.1f} | {scores}")
            lines.append(f"[系统反馈] {feedback_text}")
            probe_flag = "✓ 触发追问" if t.eval_result.is_probe_triggered else "✗ 未追问"
            lines.append(f"[追问决策] {probe_flag}" + (f" — {t.eval_result.probe_reason}" if t.eval_result.probe_reason else ""))
            lines.append("")
        lines.append("[结束语]")
        lines.append(self.closing)
        return "\n".join(lines)


def _make_session(scenario: dict) -> InterviewSession:
    interview_type = InterviewType(scenario["interview_type"])
    profile = CandidateProfile(
        name="候选人",
        target_role=scenario["target_role"],
        language=Language.ZH,
    )
    return InterviewSession(
        profile=profile,
        interview_type=interview_type,
        interview_mode=InterviewMode.DYNAMIC,
        interview_interface=InterviewInterface.TEXT,
        persona=PersonaType(scenario["persona_interviewer"]),
        active_dimensions=DEFAULT_DIMENSIONS[scenario["interview_type"]],
        candidate_profile_json=init_profile(profile),
        job_analysis=scenario["job_analysis"],
        max_questions=6,
    )


def _add_message(session: InterviewSession, role: MessageRole, content: str, **meta) -> None:
    session.messages.append(Message(
        role=role,
        content=content,
        metadata={"question_index": session.question_count, "state_at_time": session.state.value, **meta},
    ))


async def run_session(scenario: dict) -> SessionTranscript:
    session = _make_session(scenario)
    inject_short_at = scenario.get("inject_short_answer_at")  # for E2 scenario

    # ── Opening ──────────────────────────────────────────────────────────────
    session.state = InterviewState.OPENING
    apply_question(session)  # question_count = 1

    interviewer = InterviewerAgent(session)
    opening_text = await interviewer.generate_opening()
    _add_message(session, MessageRole.INTERVIEWER, opening_text)

    transcript = SessionTranscript(
        scenario_id=scenario["id"],
        persona=scenario["persona"],
        job_type=scenario["job_type"],
        target_role=scenario["target_role"],
        interview_type=scenario["interview_type"],
        interviewer_persona=scenario["persona_interviewer"],
        opening=opening_text,
    )

    last_question = opening_text
    turn_index = 1
    candidate_history: list[dict] = []  # track Q&A history for candidate memory

    # ── Main loop — mirrors interview.py respond() exactly ───────────────────
    while session.state not in (InterviewState.COMPLETED, InterviewState.CLOSING):
        is_probe_q = session.state == InterviewState.DEEP_DIVE

        # Generate candidate answer (with conversation history for consistency)
        if inject_short_at and turn_index == inject_short_at:
            candidate_answer = "我了解基本原理，但实践不多。"
        else:
            msgs = build_candidate_messages(
                scenario["persona"], scenario["target_role"], last_question,
                history=candidate_history,
            )
            candidate_answer = await candidate_chat(msgs)

        _add_message(session, MessageRole.CANDIDATE, candidate_answer)

        # Step 1: Evaluate
        evaluator = EvaluatorAgent(session)
        eval_result, profile_update = await evaluator.evaluate(
            question=last_question,
            answer=candidate_answer,
            question_index=session.question_count,
            is_probe_question=is_probe_q,
        )
        session.candidate_profile_json = merge_profile_update(
            session.candidate_profile_json, profile_update
        )
        session.evaluations.append(eval_result)

        transcript.turns.append(TurnRecord(
            turn_index=turn_index,
            question=last_question,
            candidate_answer=candidate_answer,
            is_probe=is_probe_q,
            state_label=session.state.value,
            eval_result=eval_result,
        ))

        # Update candidate history so next turn can see previous answers
        candidate_history.append({
            "question": last_question,
            "answer": candidate_answer,
        })

        # Step 2: Strategy
        strategy = StrategyAgent(session)
        decision = await strategy.decide(
            is_probe_triggered=eval_result.is_probe_triggered,
            probe_reason=eval_result.probe_reason,
        )
        next_action = decision["next_action"]
        topic = decision["topic"]

        # Step 3: State transition
        if next_action == "close":
            session.state = InterviewState.CLOSING
            break

        new_state = transition_after_answer(session, next_action)
        if next_action == "probe":
            apply_probe(session)
        session.state = new_state

        # Step 4: Generate next question
        is_probe = next_action == "probe"
        next_question = await InterviewerAgent(session).generate_response(
            next_action=next_action,
            topic=topic,
            is_probe=is_probe,
            probe_reason=eval_result.probe_reason,
            question_type=decision.get("question_type", "behavioral"),
            dimension_focus=decision.get("dimension_focus"),
        )

        if not is_probe:
            apply_question(session)

        _add_message(session, MessageRole.INTERVIEWER, next_question, is_probe=is_probe)
        last_question = next_question
        turn_index += 1

    # ── Closing ──────────────────────────────────────────────────────────────
    closing_text = await InterviewerAgent(session).generate_closing()
    session.state = InterviewState.COMPLETED
    transcript.closing = closing_text

    return transcript
