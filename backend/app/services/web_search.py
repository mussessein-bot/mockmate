import time
from app.config import TAVILY_API_KEY

_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 86400  # 24 hours
_MAX_QUERIES_PER_SEARCH = 6

_SCHOOL_DOMAIN_HINTS = {
    "上海交通大学": ["sjtu.edu.cn"],
    "上海交大": ["sjtu.edu.cn"],
    "清华大学": ["tsinghua.edu.cn"],
    "北京大学": ["pku.edu.cn"],
    "复旦大学": ["fudan.edu.cn"],
    "浙江大学": ["zju.edu.cn"],
    "南京大学": ["nju.edu.cn"],
    "中国人民大学": ["ruc.edu.cn"],
    "中国科学院大学": ["ucas.ac.cn"],
}

_DEPARTMENT_DOMAIN_HINTS = {
    ("上海交通大学", "安泰经济与管理学院"): ["acem.sjtu.edu.cn"],
    ("上海交大", "安泰经济与管理学院"): ["acem.sjtu.edu.cn"],
}


def _domain_hints(target_school: str | None, target_department: str | None) -> list[str]:
    school = target_school or ""
    department = target_department or ""
    domains: list[str] = []
    for (school_key, dept_key), vals in _DEPARTMENT_DOMAIN_HINTS.items():
        if school_key in school and dept_key in department:
            domains.extend(vals)
    for school_key, vals in _SCHOOL_DOMAIN_HINTS.items():
        if school_key in school:
            domains.extend(vals)
    return list(dict.fromkeys(domains))


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
        advisor = target_advisor or ""
        direction = research_direction or target_role or ""
        school_dept = f"{school} {dept}".strip()
        domains = _domain_hints(target_school, target_department)
        if target_advisor:
            official_domain_queries = []
            for domain in domains:
                official_domain_queries.extend([
                    f'site:{domain} "{advisor}" "{dept}"',
                    f'site:{domain}/faculty "{advisor}"',
                    f'site:{domain} "{advisor}" "{direction}"',
                ])
            return [
                # Exact phrase searches are important for common Chinese names.
                f'"{advisor}" "{school}" "{dept}" "{direction}"',
                f'"{advisor}" "{school_dept}"',
                *official_domain_queries,
                # Official school/department pages first: these are the most
                # reliable source for advisor identity and research direction.
                f"site:edu.cn {school} {dept} {advisor} 教授 研究方向",
                f"site:edu.cn {school} {dept} {advisor} 导师 简介",
                f"{school} {dept} {advisor} faculty profile research interests",
                f"{school_dept} {advisor} 教师主页 研究方向",
                f"{school_dept} {advisor} 课题组 实验室 招生",
                # Publication/profile fallback when official pages are thin.
                f"site:scholar.google.com/citations {advisor} {school}",
                f"{advisor} {school} Google Scholar",
                f"{advisor} {school} {direction} publications research",
                # Interview-prep context remains useful, but should not be the
                # only source for graduate advisor analysis.
                f"{school_dept} 研究生面试 夏令营 推免 面经",
            ]
        else:
            official_domain_queries = []
            for domain in domains:
                official_domain_queries.extend([
                    f"site:{domain} {dept} 师资队伍 {direction}",
                    f"site:{domain}/faculty {direction}",
                    f"site:{domain} 导师 名录 {direction}",
                ])
            return [
                *official_domain_queries,
                # No specific advisor: first locate department/faculty pages.
                f"site:edu.cn {school} {dept} 师资队伍 研究方向",
                f"site:edu.cn {school} {dept} 导师 名录 {direction}",
                f"{school} {dept} faculty research interests {direction}",
                f"{school_dept} 教师主页 {direction}",
                f"{school_dept} 课题组 实验室 {direction}",
                f"{school_dept} 研究生面试 夏令营 推免 面经",
                f"{school_dept} 考察重点 面试流程 {direction}".strip(),
            ]
    else:
        # technical — caller should not invoke web search, but safe fallback
        company = target_company or ""
        return [f"{company} {target_role} 技术面 考察重点 面经".strip()]


def _format_tavily_results(results: list[dict]) -> str:
    lines = []
    for r in results:
        title = r.get("title", "")
        url = r.get("url", "")
        content = (r.get("raw_content") or r.get("content", ""))[:1200]
        lines.append(f"【{title}】\nURL: {url}\n{content}")
    return "\n\n".join(lines)


def _format_ddg_results(results: list[dict]) -> str:
    lines = []
    for r in results:
        title = r.get("title", "")
        url = r.get("href", "")
        body = r.get("body", "")[:400]
        lines.append(f"【{title}】\nURL: {url}\n{body}")
    return "\n\n".join(lines)


async def _try_tavily(queries: list[str]) -> str:
    if not TAVILY_API_KEY:
        return ""
    try:
        from tavily import AsyncTavilyClient
        client = AsyncTavilyClient(api_key=TAVILY_API_KEY)
        parts = []
        for q in queries[:_MAX_QUERIES_PER_SEARCH]:
            resp = await client.search(
                q,
                max_results=4,
                search_depth="advanced",
                include_raw_content=True,
            )
            results = resp.get("results", [])
            if results:
                parts.append(f"### 查询：{q}\n{_format_tavily_results(results)}")
        return "\n\n---\n\n".join(parts) if parts else ""
    except Exception:
        return ""


async def _try_ddg(queries: list[str]) -> str:
    import asyncio
    try:
        from duckduckgo_search import DDGS
        parts = []
        def _sync_search():
            out = []
            with DDGS(timeout=5) as ddgs:
                for q in queries[:_MAX_QUERIES_PER_SEARCH]:
                    results = list(ddgs.text(q, max_results=3))
                    if results:
                        out.append(f"### 查询：{q}\n{_format_ddg_results(results)}")
            return out
        parts = await asyncio.to_thread(_sync_search)
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
        research_direction or "",
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
