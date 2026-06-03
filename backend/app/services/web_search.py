from duckduckgo_search import DDGS

_ACADEMIC_ROLE_KEYWORDS = ["研究生", "博士", "硕士", "phd", "master", "graduate", "postdoc", "博后", "直博"]
_ACADEMIC_COMPANY_KEYWORDS = ["教授", "老师", "导师", "prof", "dr.", "实验室", "lab", "课题组"]


def _is_academic_context(target_role: str, target_company: str | None) -> bool:
    role = target_role.lower()
    company = (target_company or "").lower()
    return (
        any(kw in role for kw in _ACADEMIC_ROLE_KEYWORDS)
        or any(kw in company for kw in _ACADEMIC_COMPANY_KEYWORDS)
    )


async def search_job_info(target_role: str, target_company: str | None) -> str:
    """Search DuckDuckGo for role/company or advisor/lab info, return text snippet."""
    company_part = target_company or ""

    if _is_academic_context(target_role, target_company):
        query = f"{company_part} 研究方向 课题组 招生要求 论文".strip()
    else:
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
