from duckduckgo_search import DDGS


async def search_job_info(target_role: str, target_company: str | None) -> str:
    """Search DuckDuckGo for role/company interview info, return text snippet."""
    company_part = target_company or ""
    query = f"{company_part} {target_role} 面试 考察方向 2024 2025".strip()

    try:
        with DDGS(timeout=10) as ddgs:
            results = list(ddgs.text(query, max_results=5))
    except Exception as e:
        return f"搜索失败：{e}"

    if not results:
        return "未找到相关结果。"

    lines = []
    for r in results:
        title = r.get("title", "")
        body = r.get("body", "")[:200]
        lines.append(f"· {title}：{body}")

    return "\n".join(lines)
