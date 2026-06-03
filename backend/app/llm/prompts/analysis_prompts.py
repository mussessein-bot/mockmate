def build_analysis_prompt(
    target_role: str,
    target_company: str | None,
    job_description: str | None,
    language: str,
    extra_context: str | None = None,
) -> list[dict]:
    company_str = target_company or ("未指定公司" if language == "zh" else "unspecified company")
    jd_str = f"\n职位描述：\n{job_description}" if job_description else ""
    extra_str = f"\n\n补充信息：\n{extra_context}" if extra_context else ""

    if language == "zh":
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
