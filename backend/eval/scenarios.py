from __future__ import annotations

# ---------------------------------------------------------------------------
# Hardcoded job_analysis configs — mirrors the structure produced by
# app/llm/prompts/analysis_prompts.py, so agents consume them identically.
# ---------------------------------------------------------------------------

JOB_CONFIGS: dict[str, dict] = {
    "pm": {
        "target_role": "产品经理",
        "interview_type": "behavioral",
        "job_analysis": {
            "core_dimensions": [
                {"name": "需求分析", "description": "能否识别真实用户需求并转化为产品方案", "weight": "高"},
                {"name": "数据思维", "description": "能否用数据驱动决策，理解核心指标", "weight": "高"},
                {"name": "跨职能协作", "description": "如何与研发、设计、运营协同推进", "weight": "中"},
                {"name": "优先级判断", "description": "如何在资源有限时取舍需求", "weight": "中"},
                {"name": "产品意识", "description": "对用户体验和商业目标的平衡感", "weight": "低"},
            ],
            "interview_style": "偏行为面试，重点考察过往项目经验和产品决策思路",
            "key_tips": "准备1-2个完整的产品项目案例，包含数据支撑和决策过程",
            "summary": "互联网产品经理面试，考察用户洞察、数据分析和跨团队协作能力",
        },
    },
    "swe": {
        "target_role": "软件工程师",
        "interview_type": "technical",
        "job_analysis": {
            "core_dimensions": [
                {"name": "算法与数据结构", "description": "考察编程能力和算法思维", "weight": "高"},
                {"name": "系统设计", "description": "能否设计可扩展的系统架构", "weight": "高"},
                {"name": "项目深挖", "description": "技术决策的背景、取舍和结果", "weight": "中"},
                {"name": "计算机基础", "description": "操作系统、网络、数据库原理", "weight": "中"},
                {"name": "技术表达", "description": "能否清晰解释技术方案和权衡", "weight": "低"},
            ],
            "interview_style": "技术面为主，包含代码题和系统设计，偏考察思维过程",
            "key_tips": "注重解题思路的清晰表达，系统设计注重权衡分析",
            "summary": "软件工程师面试，重点考察算法基础、系统设计和项目经验",
        },
    },
    "graduate": {
        "target_role": "计算机科学研究生申请",
        "interview_type": "graduate",
        "job_analysis": {
            "core_dimensions": [
                {"name": "学术潜力", "description": "对研究方向的理解深度和学习能力", "weight": "高"},
                {"name": "科研基础", "description": "数学、统计、专业知识的扎实程度", "weight": "高"},
                {"name": "研究热情", "description": "对该研究方向的真实兴趣和主动了解程度", "weight": "中"},
                {"name": "表达与沟通", "description": "能否清晰阐述研究想法和问题", "weight": "中"},
                {"name": "团队适配", "description": "与课题组研究风格的契合度", "weight": "低"},
            ],
            "interview_style": "学术交流风格，偏考察研究潜力和对方向的理解",
            "key_tips": "深入了解目标导师的研究方向，准备好讨论过往科研经历",
            "summary": "研究生面试，考察学术基础、研究热情和与课题组的匹配度",
        },
    },
}


def _s(
    sid: str,
    group: str,
    persona: str,
    job_key: str,
    interviewer: str,
    description: str,
    key_assertion: str,
) -> dict:
    cfg = JOB_CONFIGS[job_key]
    return {
        "id": sid,
        "group": group,
        "persona": persona,
        "job_type": job_key,
        "target_role": cfg["target_role"],
        "interview_type": cfg["interview_type"],
        "job_analysis": cfg["job_analysis"],
        "persona_interviewer": interviewer,
        "description": description,
        "key_assertion": key_assertion,
    }


# ---------------------------------------------------------------------------
# 15 scenarios — organised by test purpose
# ---------------------------------------------------------------------------

SCENARIOS: list[dict] = [
    # ── Group A: 追问逻辑 (4) ───────────────────────────────────────────────
    _s("A1", "followup_logic", "brief_answerer",  "pm",       "marcus",
       "PM岗 + 过短回答 + 最严苛 persona，测追问触发率",
       "followup_logic.score >= 3"),

    _s("A2", "followup_logic", "brief_answerer",  "swe",      "sarah",
       "SWE岗 + 过短回答 + 宽松 persona，对比追问风格差异",
       "followup_logic.score >= 3"),

    _s("A3", "followup_logic", "offtopic_answerer", "pm",     "alex",
       "PM岗 + 离题回答，测系统是否识别并纠正离题",
       "followup_logic.score >= 3"),

    _s("A4", "followup_logic", "brief_answerer",  "graduate", "sarah",
       "学术场景 + 过短回答，测研究生流程追问逻辑",
       "followup_logic.score >= 3"),

    # ── Group B: 题目切题性 (3) ─────────────────────────────────────────────
    _s("B1", "question_relevance", "baseline", "swe",      "marcus",
       "SWE岗 + 基准候选人，正向路径验证题目与岗位匹配度",
       "question_relevance.score >= 4"),

    _s("B2", "question_relevance", "baseline", "pm",       "alex",
       "PM岗 + 基准候选人，验证产品方向题目覆盖面",
       "question_relevance.score >= 4"),

    _s("B3", "question_relevance", "baseline", "graduate", "sarah",
       "学术岗 + 基准候选人，验证学术考察维度",
       "question_relevance.score >= 4"),

    # ── Group C: 评分一致性 (3×同场景重复) ─────────────────────────────────
    _s("C1", "scoring_consistency", "vague_answerer", "pm", "marcus",
       "PM岗 + 空洞回答，第1次运行（与C2/C3对比标准差）",
       "scoring_consistency.score >= 3"),

    _s("C2", "scoring_consistency", "vague_answerer", "pm", "marcus",
       "PM岗 + 空洞回答，第2次运行（同场景重复）",
       "scoring_consistency.score >= 3"),

    _s("C3", "scoring_consistency", "vague_answerer", "pm", "marcus",
       "PM岗 + 空洞回答，第3次运行（同场景重复）",
       "scoring_consistency.score >= 3"),

    # ── Group D: 反馈可操作性 (3) ───────────────────────────────────────────
    _s("D1", "feedback_actionability", "vague_answerer",  "swe", "marcus",
       "SWE岗 + 空洞回答，测技术面反馈是否具体",
       "feedback_actionability.score >= 3"),

    _s("D2", "feedback_actionability", "verbose_messy",   "pm",  "alex",
       "PM岗 + 堆砌回答，测系统能否识别混乱结构并给出有针对性反馈",
       "feedback_actionability.score >= 3"),

    _s("D3", "feedback_actionability", "vague_answerer",  "graduate", "sarah",
       "学术岗 + 空洞回答，测学术反馈质量",
       "feedback_actionability.score >= 3"),

    # ── Group E: 基准 & 综合 (2) ────────────────────────────────────────────
    _s("E1", "baseline_sanity", "baseline", "pm", "sarah",
       "对照组：正常候选人，验证整体流程无异常，评分应在合理区间",
       "overall_score >= 3.0"),

    _s("E2", "mixed_edge", "baseline", "swe", "marcus",
       "SWE + 基准候选人，但候选人在Q3故意给出极短回答，测混合场景",
       "followup_logic.score >= 3"),
]

# E2 需要在 runner 中识别并在第3轮注入短回答，通过此标志控制
SCENARIOS[-1]["inject_short_answer_at"] = 3


def get_scenario(sid: str) -> dict:
    for s in SCENARIOS:
        if s["id"] == sid:
            return s
    raise KeyError(f"Scenario {sid!r} not found")


def get_scenarios_by_group(group: str) -> list[dict]:
    return [s for s in SCENARIOS if s["group"] == group]
