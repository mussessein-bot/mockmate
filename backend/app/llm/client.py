import json
import re
from typing import AsyncGenerator
from openai import AsyncOpenAI
from app.config import ARK_API_KEY, ARK_BASE_URL, ARK_MODEL
from app.core.exceptions import LLMError


_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=ARK_API_KEY,
            base_url=ARK_BASE_URL,
        )
    return _client


async def chat_completion(
    messages: list[dict],
    temperature: float = 0.7,
) -> str:
    """Call the LLM and return the response text."""
    try:
        response = await get_client().chat.completions.create(
            model=ARK_MODEL,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        raise LLMError(f"LLM call failed: {e}") from e


def extract_json_object(text: str) -> dict:
    """Extract a JSON object from model output, tolerating wrappers and CoT text."""
    stripped = text.strip()
    if not stripped:
        raise LLMError("LLM returned empty response while JSON was expected")

    # Prefer fenced JSON blocks when present.
    for match in re.finditer(r"```(?:json)?\s*\n?(.*?)\n?\s*```", stripped, re.DOTALL | re.IGNORECASE):
        candidate = match.group(1).strip()
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    # Fast path for strict JSON mode responses.
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    # Robust fallback: find the last parseable object in the response. JSONDecoder
    # correctly handles braces inside strings, unlike manual brace counting.
    decoder = json.JSONDecoder()
    last_obj: dict | None = None
    for match in re.finditer(r"{", stripped):
        try:
            parsed, _ = decoder.raw_decode(stripped[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            last_obj = parsed
    if last_obj is not None:
        return last_obj

    raise LLMError(f"LLM returned invalid JSON: {text[:200]}")


async def chat_completion_stream(
    messages: list[dict],
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Stream LLM response, yielding text chunks as they arrive."""
    try:
        stream = await get_client().chat.completions.create(
            model=ARK_MODEL,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception as e:
        raise LLMError(f"LLM stream failed: {e}") from e


async def chat_completion_json(messages: list[dict], temperature: float = 0.3) -> dict:
    """Call the LLM in JSON mode when available; parse and return a dict."""
    try:
        response = await get_client().chat.completions.create(
            model=ARK_MODEL,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or ""
    except Exception as e:
        msg = str(e).lower()
        if "response_format" not in msg and "json_object" not in msg:
            raise LLMError(f"LLM JSON call failed: {e}") from e
        # Some OpenAI-compatible providers/models do not expose JSON mode. In
        # that case keep one resilient fallback path instead of failing hard.
        text = await chat_completion(messages, temperature=temperature)

    return extract_json_object(text)
