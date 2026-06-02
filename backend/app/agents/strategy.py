from app.agents.base import BaseAgent
from app.core.models import InterviewSession, InterviewMode
from app.core.memory import profile_to_text
from app.core.state_machine import can_probe
from app.llm.client import chat_completion_json
from app.llm.prompts.strategy_prompts import build_strategy_prompt


class StrategyAgent(BaseAgent):
    async def decide(
        self,
        is_probe_triggered: bool,
        probe_reason: str | None,
    ) -> dict:
        """
        Returns {next_action, topic, dimension_focus, question_type, reasoning}.
        next_action: "continue" | "probe" | "close"
        question_type: "behavioral" | "situational" | "quantitative_probe" | "role_challenge"
        """
        profile_text = profile_to_text(self.session.candidate_profile_json, self.language)
        probe_allowed = can_probe(self.session)

        topics_covered = self.session.candidate_profile_json.get("topics_covered", [])
        recent_non_probe = [e for e in self.session.evaluations if not e.is_probe]
        recent_scores = [e.overall_score for e in recent_non_probe[-3:]]

        messages = build_strategy_prompt(
            state=self.session.state.value,
            question_count=self.session.question_count,
            max_questions=self.session.max_questions,
            probe_count=self.session.probe_count,
            can_probe=probe_allowed,
            is_probe_triggered=is_probe_triggered,
            probe_reason=probe_reason,
            interview_type=self.session.interview_type.value,
            interview_mode=self.session.interview_mode.value,
            active_dimensions=self.session.active_dimensions,
            profile_text=profile_text,
            recent_messages=self.recent_messages,
            language=self.language,
            topics_covered=topics_covered,
            recent_scores=recent_scores,
        )

        data = await chat_completion_json(messages, temperature=0.4)

        next_action = data.get("next_action", "continue")

        # Hard limit: force close at max_questions in dynamic mode
        if (self.session.interview_mode == InterviewMode.DYNAMIC
                and self.session.question_count >= self.session.max_questions):
            next_action = "close"

        # Enforce: "close" only allowed in dynamic mode
        elif next_action == "close" and self.session.interview_mode != InterviewMode.DYNAMIC:
            next_action = "continue"

        # Enforce: "probe" only when can_probe
        if next_action == "probe" and not probe_allowed:
            next_action = "continue"

        return {
            "next_action": next_action,
            "topic": data.get("topic", ""),
            "dimension_focus": data.get("dimension_focus", []),
            "question_type": data.get("question_type", "behavioral"),
            "reasoning": data.get("reasoning", ""),
        }
