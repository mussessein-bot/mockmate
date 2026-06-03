import time
from app.config import TAVILY_API_KEY

_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 86400  # 24 hours


def _build_queries(
    interview_type: str,
    target_role: str,
    target_company: str | None,
    target_school: str | None,
    target_department: str | None,
    target_advisor: str | None,
    research_direction: str | None,
) -> list[str]:
    if interview_type == "behavioral":
        company = target_company or ""
        base = f"{company} {target_role}".strip()
        return [
            f"{base} 行为面试 面经 真题 2024 2025",
            f"site:nowcoder.com {base} 面经",
        ]
    elif interview_type == "graduate":
        school = target_school or ""
        dept = target_department or ""
        if target_advisor:
            return [
                f"{school} {dept} 研究生面试 夏令营 推免 面经",
                f"{target_advisor} 导师 研究方向 研究生面试 招生要求",
            ]
        else:
            return [
                f"{school} {dept} 研究生面试 夏令营 推免 面经",
                f"{school} {dept} 考察重点 面试流程 {research_direction or ''}".strip(),
            ]
    else:
        # technical — caller should not invoke web search, but safe fallback
        company = target_company or ""
        return [f"{company} {target_role} 技术面 考察重点 面经".strip()]


def _format_tavily_results(results: list[dict]) -> str:
    lines = []
    for r in results:
        title = r.get("title", "")
        content = r.get("content", "")[:500]
        lines.append(f"【{title}】\n{content}")
    return "\n\n".join(lines)


def _format_ddg_results(results: list[dict]) -> str:
    lines = []
    for r in results:
        title = r.get("title", "")
        body = r.get("body", "")[:400]
        lines.append(f"【{title}】\n{body}")
    return "\n\n".join(lines)


async def _try_tavily(queries: list[str]) -> str:
    if not TAVILY_API_KEY:
        return ""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)
        parts = []
        for q in queries:
            resp = client.search(q, max_results=4, search_depth="basic")
            results = resp.get("results", [])
            if results:
                parts.append(_format_tavily_results(results))
        return "\n\n---\n\n".join(parts) if parts else ""
    except Exception:
        return ""


async def _try_ddg(queries: list[str]) -> str:
    try:
        from duckduckgo_search import DDGS
        parts = []
        with DDGS(timeout=10) as ddgs:
            for q in queries:
                results = list(ddgs.text(q, max_results=4))
                if results:
                    parts.append(_format_ddg_results(results))
        return "\n\n---\n\n".join(parts) if parts else ""
    except Exception:
        return ""


async def search_interview_info(
    interview_type: str,
    target_role: str,
    target_company: str | None = None,
    target_school: str | None = None,
    target_department: str | None = None,
    target_advisor: str | None = None,
    research_direction: str | None = None,
) -> str:
    """Three-layer search: Tavily → DuckDuckGo → empty string (caller degrades gracefully)."""
    cache_key = "|".join([
        interview_type, target_role,
        target_company or "", target_school or "",
        target_department or "", target_advisor or "",
    ])
    if cache_key in _cache:
        text, ts = _cache[cache_key]
        if time.time() - ts < _CACHE_TTL:
            return text

    queries = _build_queries(
        interview_type, target_role, target_company,
        target_school, target_department, target_advisor, research_direction,
    )

    result = await _try_tavily(queries)
    if not result:
        result = await _try_ddg(queries)

    if result:
        _cache[cache_key] = (result, time.time())
    return result


# Kept for backward-compat (refine-analysis still uses this)
async def search_job_info(target_role: str, target_company: str | None) -> str:
    return await search_interview_info(
        interview_type="behavioral",
        target_role=target_role,
        target_company=target_company,
    )
