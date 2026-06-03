import json
import re
import httpx
from openai import OpenAI

import eval  # noqa: F401 — triggers sys.path bootstrap
from app.config import ARK_API_KEY, ARK_BASE_URL

CANDIDATE_MODEL = "doubao-seed-2.0-lite"
JUDGE_MODEL = "deepseek-v4-pro"

_candidate_client: OpenAI | None = None
_judge_client: OpenAI | None = None


def _make_client(model: str) -> OpenAI:
    return OpenAI(
        api_key=ARK_API_KEY,
        base_url=ARK_BASE_URL,
        http_client=httpx.Client(trust_env=False),
    )


def _get_candidate() -> OpenAI:
    global _candidate_client
    if _candidate_client is None:
        _candidate_client = _make_client(CANDIDATE_MODEL)
    return _candidate_client


def _get_judge() -> OpenAI:
    global _judge_client
    if _judge_client is None:
        _judge_client = _make_client(JUDGE_MODEL)
    return _judge_client


def candidate_chat(messages: list[dict], temperature: float = 0.85) -> str:
    resp = _get_candidate().chat.completions.create(
        model=CANDIDATE_MODEL,
        messages=messages,
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""


def judge_chat(messages: list[dict]) -> dict:
    resp = _get_judge().chat.completions.create(
        model=JUDGE_MODEL,
        messages=messages,
        temperature=0,
    )
    text = resp.choices[0].message.content or ""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    # Find last complete JSON object
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
