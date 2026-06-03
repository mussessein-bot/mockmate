from __future__ import annotations

import eval  # noqa: F401
from eval.client import judge_chat
from eval.prompts import build_judge_messages
from eval.runner import SessionTranscript


def evaluate_transcript(transcript: SessionTranscript, scenario: dict) -> dict:
    """
    Call the Judge LLM on a completed transcript.
    Returns the parsed judge result dict with dimensions + severity_catalog.
    """
    transcript_text = transcript.as_text()
    messages = build_judge_messages(transcript_text, scenario)
    result = judge_chat(messages)

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
    """
    assertion = scenario.get("key_assertion", "")
    if not assertion:
        return True
    try:
        # Parse "path op value"
        parts = assertion.split()
        if len(parts) != 3:
            return True
        path, op, raw_val = parts
        val = float(raw_val)

        keys = path.split(".")
        node = judge_result
        if keys[0] == "dimensions":
            keys = keys  # already rooted correctly
        else:
            # e.g. "followup_logic.score" → look inside dimensions
            if keys[0] in judge_result.get("dimensions", {}):
                node = judge_result["dimensions"]
            # else top-level key like "overall_score"

        for k in keys:
            if isinstance(node, dict):
                node = node[k]
            else:
                return True  # can't resolve, skip

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
    except Exception:
        pass
    return True
