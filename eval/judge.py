from __future__ import annotations

import logging

import eval  # noqa: F401
from eval.client import judge_chat
from eval.prompts import build_judge_messages
from eval.runner import SessionTranscript

logger = logging.getLogger(__name__)


async def evaluate_transcript(transcript: SessionTranscript, scenario: dict) -> dict:
    """
    Call the Judge LLM on a completed transcript (async).
    Returns the parsed judge result dict with dimensions + severity_catalog.
    """
    transcript_text = transcript.as_text()
    messages = build_judge_messages(transcript_text, scenario)
    result = await judge_chat(messages)

    # Attach metadata for reporting
    result["scenario_id"] = transcript.scenario_id
    result["persona"] = transcript.persona
    result["job_type"] = transcript.job_type
    result["turn_count"] = len(transcript.turns)

    return result


def extract_high_issues(judge_result: dict) -> list[dict]:
    return [
        item for item in judge_result.get("severity_catalog", [])
        if item.get("severity") == "HIGH"
    ]


def passes_key_assertion(judge_result: dict, scenario: dict) -> bool:
    """
    Evaluate the scenario's key_assertion string against judge_result.
    Supports simple dot-path comparisons like "followup_logic.score >= 3"
    and "overall_score >= 3.0".

    Returns False on parse failure (fail-closed: suspicious results surface
    immediately rather than being silently accepted).
    """
    assertion = scenario.get("key_assertion", "")
    if not assertion:
        return True
    try:
        # Parse "path op value"
        parts = assertion.split()
        if len(parts) != 3:
            logger.warning("Invalid assertion format: %r", assertion)
            return False
        path, op, raw_val = parts
        val = float(raw_val)

        keys = path.split(".")
        node = judge_result

        # Navigate: "followup_logic.score" → dimensions.followup_logic.score
        if keys[0] in judge_result.get("dimensions", {}):
            node = judge_result["dimensions"]

        for k in keys:
            if isinstance(node, dict):
                if k not in node:
                    logger.warning("Assertion path %r not found in judge result", path)
                    return False
                node = node[k]
            else:
                logger.warning("Cannot navigate assertion path %r at key %r", path, k)
                return False

        actual = float(node)
        if op == ">=":
            return actual >= val
        if op == "<=":
            return actual <= val
        if op == ">":
            return actual > val
        if op == "<":
            return actual < val
        if op == "==":
            return actual == val
        logger.warning("Unknown operator in assertion: %r", op)
        return False
    except (ValueError, TypeError) as e:
        logger.warning("Failed to evaluate assertion %r: %s", assertion, e)
        return False
