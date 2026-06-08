import json
import re
import logging
import httpx
from openai import AsyncOpenAI

import eval  # noqa: F401 — triggers sys.path bootstrap
from app.config import ARK_API_KEY, ARK_BASE_URL

logger = logging.getLogger(__name__)

CANDIDATE_MODEL = "doubao-seed-2.0-lite"
JUDGE_MODEL = "deepseek-v4-pro"

_candidate_client: AsyncOpenAI | None = None
_judge_client: AsyncOpenAI | None = None


def _make_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=ARK_API_KEY,
        base_url=ARK_BASE_URL,
        http_client=httpx.AsyncClient(trust_env=False),
    )


def _get_candidate() -> AsyncOpenAI:
    global _candidate_client
    if _candidate_client is None:
        _candidate_client = _make_client()
    return _candidate_client


def _get_judge() -> AsyncOpenAI:
    global _judge_client
    if _judge_client is None:
        _judge_client = _make_client()
    return _judge_client


async def candidate_chat(messages: list[dict], temperature: float = 0.85) -> str:
    """Generate a candidate answer (async)."""
    try:
        resp = await _get_candidate().chat.completions.create(
            model=CANDIDATE_MODEL,
            messages=messages,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.warning("candidate_chat API error: %s", e)
        return "抱歉，我没有太理解这个问题。"


async def judge_chat(messages: list[dict]) -> dict:
    """Call the Judge LLM and parse structured JSON from response (async).

    The Judge outputs reasoning text before the JSON block (CoT).
    We extract the JSON by looking for ```json...``` blocks first,
    then falling back to finding the last complete JSON object.
    """
    resp = await _get_judge().chat.completions.create(
        model=JUDGE_MODEL,
        messages=messages,
        temperature=0,
    )
    text = resp.choices[0].message.content or ""
    return _parse_judge_json(text)


def _parse_judge_json(text: str) -> dict:
    """Extract JSON from Judge response, handling CoT text before JSON."""
    stripped = text.strip()

    # Strategy 1: Look for ```json ... ``` code block
    json_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", stripped, re.DOTALL)
    if json_block_match:
        try:
            return json.loads(json_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 2: Find last complete JSON object (walk braces)
    last_close = stripped.rfind("}")
    if last_close != -1:
        depth = 0
        for i in range(last_close, -1, -1):
            if stripped[i] == "}":
                depth += 1
            elif stripped[i] == "{":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(stripped[i : last_close + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"judge_chat: no valid JSON in response: {text[:300]}")
