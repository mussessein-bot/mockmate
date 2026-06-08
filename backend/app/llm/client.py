import json
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
    """Call the LLM expecting a JSON response; parse and return dict."""
    text = await chat_completion(messages, temperature=temperature)
    # Strip markdown code fences if model wraps output
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM returned invalid JSON: {text[:200]}") from e
