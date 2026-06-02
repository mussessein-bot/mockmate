import re
import json
from app.agents.base import BaseAgent
from app.core.models import InterviewSession, DimensionScore, EvaluationResult
from app.core.memory import merge_profile_update, profile_to_text
from app.core.state_machine import can_probe
from app.core.dimensions import DIMENSION_POOL
from app.core.exceptions import LLMError
from app.llm.client import chat_completion
from app.llm.prompts.evaluator_prompts import build_evaluator_prompt


def _extract_json(text: str) -> dict:
    """Extract the last complete JSON object from a CoT-style LLM response."""
    # Try markdown code fence first
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Find the last complete { ... } block by scanning backwards
    last_close = text.rfind('}')
    if last_close == -1:
        raise LLMError(f"No JSON found in evaluator response: {text[:200]}")
    depth = 0
    for i in range(last_close, -1, -1):
        if text[i] == '}':
            depth += 1
        elif text[i] == '{':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[i:last_close + 1])
                except json.JSONDecodeError as e:
                    raise LLMError(f"Malformed JSON in evaluator response: {e}") from e
    raise LLMError(f"Malformed JSON in evaluator response: {text[:200]}")


class EvaluatorAgent(BaseAgent):
    async def evaluate(
        self,
        question: str,
        answer: str,
        question_index: int,
        is_probe_question: bool,
    ) -> tuple[EvaluationResult, dict]:
        """
        Evaluate a candidate answer.
        Returns (EvaluationResult, profile_update_dict).
        """
        profile_text = profile_to_text(self.session.candidate_profile_json, self.language)
        probe_allowed = can_probe(self.session) and not is_probe_question

        messages = build_evaluator_prompt(
            question=question,
            answer=answer,
            active_dimensions=self.session.active_dimensions,
            dimension_pool=DIMENSION_POOL,
            profile_text=profile_text,
            language=self.language,
            can_probe=probe_allowed,
        )

        raw = await chat_completion(messages, temperature=0.1)
        data = _extract_json(raw)

        # Parse dimension scores
        scores = []
        for s in data.get("dimension_scores", []):
            if s.get("dimension") in self.session.active_dimensions:
                scores.append(DimensionScore(
                    dimension=s["dimension"],
                    score=float(s.get("score", 5.0)),
                    feedback=s.get("feedback", ""),
                ))

        overall = float(data.get("overall_score", sum(s.score for s in scores) / max(len(scores), 1)))
        is_triggered = bool(data.get("is_probe_triggered", False)) and probe_allowed

        result = EvaluationResult(
            question_index=question_index,
            question_text=question,
            answer_transcript=answer,
            dimension_scores=scores,
            overall_score=overall,
            is_probe=is_probe_question,
            is_probe_triggered=is_triggered,
            probe_reason=data.get("probe_reason"),
        )

        profile_update = data.get("profile_update", {})
        return result, profile_update
