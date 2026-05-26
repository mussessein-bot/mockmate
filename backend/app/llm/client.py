import json
from openai import AsyncOpenAI
from app.config import ARK_API_KEY, ARK_BASE_URL, ARK_MODEL
from app.core.exceptions import LLMError


_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=ARK_API_KEY, base_url=ARK_BASE_URL)
    return _client


async def chat_completion(
    messages: list[dict],
    temperature: float = 0.7,
    json_mode: bool = False,
) -> str:
    """Call the LLM and return the response text."""
    kwargs: dict = {
        "model": ARK_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = await get_client().chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""
    except Exception as e:
        raise LLMError(f"LLM call failed: {e}") from e


async def chat_completion_json(messages: list[dict], temperature: float = 0.3) -> dict:
    """Call the LLM expecting a JSON response; parse and return dict."""
    text = await chat_completion(messages, temperature=temperature, json_mode=True)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM returned invalid JSON: {text[:200]}") from e
