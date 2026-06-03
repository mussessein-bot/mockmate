_ACADEMIC_ROLE_KEYWORDS = ["研究生", "博士", "硕士", "phd", "master", "graduate", "postdoc", "博后", "直博"]
_ACADEMIC_COMPANY_KEYWORDS = ["教授", "老师", "导师", "prof", "dr.", "实验室", "lab", "课题组"]


def _is_academic_context(target_role: str, target_company: str | None) -> bool:
    role = target_role.lower()
    company = (target_company or "").lower()
    return (
        any(kw in role for kw in _ACADEMIC_ROLE_KEYWORDS)
        or any(kw in company for kw in _ACADEMIC_COMPANY_KEYWORDS)
    )


def build_analysis_prompt(
    target_role: str,
    target_company: str | None,
    job_description: str | None,
    language: str,
    extra_context: str | None = None,
) -> list[dict]:
    company_str = target_company or ("未指定导师/公司" if language == "zh" else "unspecified advisor/company")
    jd_str = f"\n职位/申请描述：\n{job_description}" if job_description else ""
    extra_str = f"\n\n补充信息：\n{extra_context}" if extra_context else ""

    academic = _is_academic_context(target_role, target_company)

    if language == "zh":
        if academic:
            system = """你是一名研究生申请顾问，擅长分析导师的研究方向和课题组特点，帮助申请者做面试准备。
请根据输入的导师/课题组信息，输出结构化的面试分析，帮助申请者了解面试重点。
输出严格的 JSON，不要输出任何其他文字：
{
  "core_dimensions": [
    {"name": "维度名称", "description": "具体考察内容（1-2句）", "weight": "高|中|低"}
  ],
  "interview_style": "面试风格描述（1句话，如：重点考察科研潜力，偏学术交流风格）",
  "key_tips": "申请者准备建议（1-2句，聚焦如何展示与该导师研究方向的契合度）",
  "summary": "该课题组/导师面试一句话总结"
}
core_dimensions 输出 3-5 个，重点围绕：研究方向匹配、学术基础、科研潜力、沟通表达、对课题组的了解，按重要性从高到低排列。"""

            user = f"""请分析以下导师/课题组研究生面试的重点：
导师/课题组：{company_str}
申请方向：{target_role}{jd_str}{extra_str}"""
        else:
            system = """你是一名专业的求职顾问，擅长分析岗位要求并帮助候选人做面试准备。
请根据输入的岗位信息，输出结构化的岗位分析，帮助候选人了解面试重点。
输出严格的 JSON，不要输出任何其他文字：
{
  "core_dimensions": [
    {"name": "维度名称", "description": "具体考察内容（1-2句）", "weight": "高|中|低"}
  ],
  "interview_style": "面试风格描述（1句话，如：偏压力测试，注重数据量化）",
  "key_tips": "候选人准备建议（1-2句）",
  "summary": "岗位一句话总结"
}
core_dimensions 输出 3-5 个，按考察权重从高到低排列。"""

            user = f"""请分析以下岗位的面试重点：
公司：{company_str}
职位：{target_role}{jd_str}{extra_str}"""

    else:
        if academic:
            system = """You are a graduate school application consultant skilled at analyzing professors' research areas and lab characteristics.
Analyze the given advisor/lab information and output a structured interview analysis to help the applicant understand the key focus areas.
Output strict JSON only, no other text:
{
  "core_dimensions": [
    {"name": "dimension name", "description": "specific assessment content (1-2 sentences)", "weight": "high|medium|low"}
  ],
  "interview_style": "interview style (1 sentence, e.g.: focuses on research potential, academic discussion style)",
  "key_tips": "preparation advice (1-2 sentences, focused on demonstrating fit with the advisor's research)",
  "summary": "one-sentence summary of this lab/advisor interview"
}
Output 3-5 core_dimensions covering: research direction fit, academic background, research potential, communication, lab knowledge. Sort by importance."""

            user = f"""Analyze the key interview focus areas for this graduate student position:
Advisor/Lab: {company_str}
Application area: {target_role}{jd_str}{extra_str}"""
        else:
            system = """You are a professional career consultant skilled at analyzing job requirements and helping candidates prepare for interviews.
Analyze the given job information and output a structured role analysis to help the candidate understand the interview focus areas.
Output strict JSON only, no other text:
{
  "core_dimensions": [
    {"name": "dimension name", "description": "specific assessment content (1-2 sentences)", "weight": "high|medium|low"}
  ],
  "interview_style": "interview style (1 sentence, e.g.: pressure-testing, data-focused)",
  "key_tips": "preparation advice for the candidate (1-2 sentences)",
  "summary": "one-sentence role summary"
}
Output 3-5 core_dimensions, sorted by assessment weight from high to low."""

            user = f"""Analyze the interview focus areas for this role:
Company: {company_str}
Role: {target_role}{jd_str}{extra_str}"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_extraction_prompt(search_text: str, interview_type: str, language: str) -> list[dict]:
    """Extract real interview questions from raw search results."""
    if language == "zh":
        type_hint = {
            "behavioral": "行为面试题（STAR 格式）",
            "graduate": "研究生面试题（学术动机、科研经历、专业知识等）",
            "technical": "技术面试题（算法、系统设计、技术概念等）",
        }.get(interview_type, "面试题")
        system = f"""你是一个面试题提取助手。从网络搜索结果中提取真实的{type_hint}。
要求：
- 只提取明确的面试题目，不提取经验叙述、答案或评价
- 去重，合并措辞相似的题目
- 按类别分组（如自我介绍、项目经历、情景题、专业知识等）
- 若内容中没有有效题目，返回空列表
输出严格 JSON，不含其他文字：
{{"questions": [{{"category": "类别名", "question": "具体题目"}}]}}"""
        user = f"请从以下搜索内容中提取面试题目：\n\n{search_text}"
    else:
        type_hint = {
            "behavioral": "behavioral interview questions (STAR format)",
            "graduate": "graduate school interview questions (research motivation, academic background)",
            "technical": "technical interview questions (algorithms, system design, concepts)",
        }.get(interview_type, "interview questions")
        system = f"""You are an interview question extractor. Extract real {type_hint} from web search results.
Rules:
- Only extract clear interview questions, not personal narratives, answers, or evaluations
- Deduplicate and merge similar questions
- Group by category (e.g. self-introduction, project experience, situational, technical knowledge)
- Return empty list if no valid questions found
Output strict JSON only:
{{"questions": [{{"category": "category name", "question": "specific question"}}]}}"""
        user = f"Extract interview questions from the following search content:\n\n{search_text}"

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
