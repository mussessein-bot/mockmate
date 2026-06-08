STRATEGY_SYSTEM_ZH = """你是面试策略规划师。根据当前面试进度和评估结果，决定下一步行动。

输出严格的 JSON，格式如下：
{
  "next_action": "continue" | "probe" | "close",
  "topic": "下一个话题的简短描述（如果 next_action 是 probe，填写追问关注点）",
  "dimension_focus": ["维度key1", "维度key2"],
  "question_type": "behavioral" | "situational" | "quantitative_probe" | "role_challenge" | "technical_concept" | "algorithm" | "system_design",
  "reasoning": "一句话说明原因"
}

## 问题类型说明
- behavioral：行为面试题，"能描述一次……的经历吗？"（适合全部面试官，Sarah 首选）
- situational：情景假设题，"如果……你会怎么做？"（Alex 首选，考察临场判断）
- quantitative_probe：量化追问，追问数字来源、具体规模、衡量方式（Marcus 首选）
- role_challenge：角色挑战题，挑战候选人的立场或假设，"你真的认为……吗？"（Marcus/Alex 首选）
- technical_concept：技术概念题，考察原理和底层知识（技术面专用，如"解释一下 GC 机制"）
- algorithm：算法题，给出具体题目让候选人分析思路（技术面专用，禁止直接给答案）
- system_design：系统设计题，让候选人设计一个系统或模块（技术面专用）

技术面（interview_type=technical）question_type 建议分布：技术基础阶段用 technical_concept，核心阶段用 algorithm 或 system_design，收尾阶段用 quantitative_probe 追问项目细节。

## 行动规则

规则1："probe" — 仅当 can_probe=true 时可选；当 is_probe_triggered=true 时优先选择
  → 为什么：超出配额的追问会打断面试节奏，让候选人感到被针对
  → 反例：即使 is_probe_triggered=true，若 can_probe=false，也必须选 continue

规则2："close" — 仅动态模式且主题题数 >= 6 时可选；question_count >= max_questions 时必选；预设模式禁止选
  → 为什么：预设模式由状态机控制结束，策略层无需干预；提前关闭会漏测关键维度
  → 反例：动态模式下若仍有重要维度未覆盖，不应在6题就选 close

规则3："continue" — 继续下一道正式题，是最常见选择
  → 为什么：保持节奏，确保维度覆盖的广度

规则4：dimension_focus 必须从 active_dimensions 中选1-2个
  → 为什么：超出激活维度的评分无意义，浪费面试时间
  → 反例：不能因为"感觉重要"就选未激活的维度

规则5：topic 必须具体，给面试官明确方向
  → 为什么：模糊 topic（如"领导力"）会导致面试官提出同质化问题
  → 正确示例："带跨部门团队应对线上事故并协调多方资源的经历"
  → 反例："领导力"、"沟通能力"等抽象标签"""

STRATEGY_SYSTEM_EN = """You are an interview strategy planner. Based on the current interview progress and evaluation, decide the next action.

Output strict JSON only:
{
  "next_action": "continue" | "probe" | "close",
  "topic": "Brief description of the next topic (if probing, describe the follow-up focus)",
  "dimension_focus": ["dimension_key1", "dimension_key2"],
  "question_type": "behavioral" | "situational" | "quantitative_probe" | "role_challenge" | "technical_concept" | "algorithm" | "system_design",
  "reasoning": "One sentence explanation"
}

## Question Type Definitions
- behavioral: Behavioral interview question — "Tell me about a time when..." (universal; Sarah's preference)
- situational: Hypothetical scenario — "If X happened, what would you do?" (Alex's preference; tests in-the-moment judgment)
- quantitative_probe: Probe for numbers — source, scale, measurement method (Marcus's preference)
- role_challenge: Challenge the candidate's position or assumption — "Do you really think...? Why?" (Marcus/Alex preference)
- technical_concept: Technical concept question — probe underlying principles (technical interviews only, e.g. "Explain the GC mechanism")
- algorithm: Algorithm problem — present a specific problem for the candidate to analyze (technical interviews only; never give away the answer)
- system_design: System design question — have the candidate design a system or component (technical interviews only)

For technical interviews (interview_type=technical): prefer technical_concept in early rounds, algorithm or system_design in core rounds, quantitative_probe for project deep-dives.

## Action Rules

Rule 1: "probe" — only when can_probe=true; prioritize when is_probe_triggered=true
  → Why: Probing beyond quota disrupts interview rhythm and makes candidates feel targeted
  → Counterexample: Even if is_probe_triggered=true, if can_probe=false — must choose continue

Rule 2: "close" — dynamic mode only, when main questions >= 6; MUST choose when question_count >= max_questions; forbidden in preset mode
  → Why: Preset mode uses state machine to control ending; premature close misses key dimensions
  → Counterexample: In dynamic mode, if important dimensions are still uncovered, don't close at 6

Rule 3: "continue" — next main question, the most common choice
  → Why: Maintains pace and ensures breadth of dimension coverage

Rule 4: dimension_focus must be 1-2 keys from active_dimensions
  → Why: Scoring outside active dimensions is meaningless and wastes interview time
  → Counterexample: Don't pick a dimension just because it "feels important" if it's not active

Rule 5: topic must be specific, giving the interviewer clear direction
  → Why: Vague topics (e.g., "leadership") cause the interviewer to ask generic, repetitive questions
  → Good: "Led a cross-team incident response while coordinating multiple stakeholders"
  → Bad: "leadership", "communication skills" (too abstract)"""


STRATEGY_SYSTEM_ZH += """

## Memory Use Rules
- Treat covered topics as structured memory. Do not choose a next topic with the same topic + dimension + question_type combination.
- If a topic was already probed, do not probe it again unless the latest answer introduced a clear contradiction.
- Prefer uncovered active dimensions. If all active dimensions have been covered, prefer the lowest recent score.
- When selecting a topic, explain in reasoning which memory gap it addresses."""
STRATEGY_SYSTEM_EN += """

## Memory Use Rules
- Treat covered topics as structured memory. Do not choose a next topic with the same topic + dimension + question_type combination.
- If a topic was already probed, do not probe it again unless the latest answer introduced a clear contradiction.
- Prefer uncovered active dimensions. If all active dimensions have been covered, prefer the lowest recent score.
- When selecting a topic, explain in reasoning which memory gap it addresses."""


def _phase_instruction_zh(question_count: int, max_questions: int, interview_type: str = "behavioral") -> str:
    if interview_type == "technical":
        if question_count <= 2:
            return "【技术面阶段：背景了解】先询问候选人的核心项目经历和技术栈，不要上难题，建立基础认知。"
        elif question_count <= 5:
            return "【技术面阶段：核心考察】穿插技术基础题和算法/系统设计题，question_type 优先用 quantitative_probe；追问复杂度和技术选型理由。"
        elif question_count >= max_questions - 2:
            return "【技术面阶段：深挖收尾】项目技术决策深挖，可以上一道系统设计题；确认候选人最薄弱的技术方向。"
        else:
            return "【技术面阶段：深度考察】加深技术难度，聚焦项目实战中的技术挑战和解决方案。"
    if question_count <= 2:
        return "【当前阶段：开场探索】广泛覆盖不同维度，不要深挖任何单一话题，先摸清候选人整体面貌。"
    elif question_count >= max_questions - 2:
        return "【当前阶段：收尾确认】面试即将结束，重点确认1-2个评分最低的维度，给候选人最后展示机会。"
    else:
        return "【当前阶段：核心考察】优先针对弱项维度，避免重复已覆盖话题，可适当加深难度。"


def _phase_instruction_en(question_count: int, max_questions: int, interview_type: str = "behavioral") -> str:
    if interview_type == "technical":
        if question_count <= 2:
            return "[Tech Interview Phase: Background] Ask about core projects and tech stack first. No hard questions yet — build baseline understanding."
        elif question_count <= 5:
            return "[Tech Interview Phase: Core Assessment] Mix fundamentals with algorithm/system design questions. Prefer quantitative_probe question type; probe for complexity and tech trade-offs."
        elif question_count >= max_questions - 2:
            return "[Tech Interview Phase: Deep-Dive Closing] Project technical decision deep-dive; consider a system design question. Confirm the candidate's weakest technical areas."
        else:
            return "[Tech Interview Phase: Advanced] Increase technical difficulty; focus on real-world challenges and solutions from their projects."
    if question_count <= 2:
        return "[Phase: Broad Exploration] Cover multiple dimensions broadly — do NOT deep-dive on any single topic yet. Get an overall picture of the candidate first."
    elif question_count >= max_questions - 2:
        return "[Phase: Closing Confirmation] Interview is near the end. Focus on confirming 1-2 lowest-scoring dimensions. Give the candidate a final chance to demonstrate their capabilities."
    else:
        return "[Phase: Core Assessment] Prioritize weak-area dimensions. Avoid repeating topics already covered. Incrementally increase depth."


def _difficulty_instruction_zh(recent_scores: list[float]) -> str:
    if not recent_scores:
        return ""
    avg = sum(recent_scores) / len(recent_scores)
    if avg >= 8.0:
        return f"【难度调整：提升】最近{len(recent_scores)}题均分{avg:.1f}，候选人表现优秀，请选择更抽象的场景或极端假设，提升考察深度。"
    elif avg <= 5.0:
        return f"【难度调整：降低】最近{len(recent_scores)}题均分{avg:.1f}，候选人需要更多引导，请选择有脚手架支撑的引导性问题，帮助候选人展示真实能力。"
    return f"【难度调整：标准】最近{len(recent_scores)}题均分{avg:.1f}，保持当前难度。"


def _difficulty_instruction_en(recent_scores: list[float]) -> str:
    if not recent_scores:
        return ""
    avg = sum(recent_scores) / len(recent_scores)
    if avg >= 8.0:
        return f"[Difficulty: Increase] Avg score {avg:.1f} over last {len(recent_scores)} questions — candidate is performing well. Use more abstract scenarios or extreme hypotheticals to increase depth."
    elif avg <= 5.0:
        return f"[Difficulty: Decrease] Avg score {avg:.1f} over last {len(recent_scores)} questions — candidate needs scaffolding. Use guided questions that help them demonstrate their real capabilities."
    return f"[Difficulty: Standard] Avg score {avg:.1f} — maintain current difficulty."


def _job_analysis_text_zh(job_analysis: dict) -> str:
    dims = job_analysis.get("core_dimensions", [])
    if not dims:
        return ""
    lines = ["【岗位核心考察方向】请优先围绕以下方向选择话题："]
    for d in dims:
        lines.append(f"- {d['name']}（权重：{d.get('weight','中')}）：{d.get('description','')}")
    return "\n".join(lines)


def _job_analysis_text_en(job_analysis: dict) -> str:
    dims = job_analysis.get("core_dimensions", [])
    if not dims:
        return ""
    lines = ["[Job Focus Areas] Prioritize topics aligned with these dimensions:"]
    for d in dims:
        lines.append(f"- {d['name']} (weight: {d.get('weight','medium')}): {d.get('description','')}")
    return "\n".join(lines)


def build_strategy_prompt(
    state: str,
    question_count: int,
    max_questions: int,
    probe_count: int,
    can_probe: bool,
    is_probe_triggered: bool,
    probe_reason: str | None,
    interview_type: str,
    interview_mode: str,
    active_dimensions: list[str],
    profile_text: str,
    recent_messages: list[dict],
    language: str,
    topics_covered: list[str] | None = None,
    recent_scores: list[float] | None = None,
    job_analysis: dict | None = None,
) -> list[dict]:
    system = STRATEGY_SYSTEM_ZH if language == "zh" else STRATEGY_SYSTEM_EN

    msgs_text = "\n".join(
        f"[{m['role']}]: {m['content'][:200]}" for m in recent_messages[-6:]
    )

    phase_instr = (
        _phase_instruction_zh(question_count, max_questions, interview_type)
        if language == "zh"
        else _phase_instruction_en(question_count, max_questions, interview_type)
    )

    difficulty_instr = (
        _difficulty_instruction_zh(recent_scores or [])
        if language == "zh"
        else _difficulty_instruction_en(recent_scores or [])
    )
    difficulty_line = f"\n{difficulty_instr}" if difficulty_instr else ""

    ja = job_analysis or {}
    if language == "zh":
        ja_text = _job_analysis_text_zh(ja)
        ja_line = f"\n\n{ja_text}" if ja_text else ""
        exclusion = f"\n已覆盖话题（不要重复出题）：{', '.join(topics_covered)}" if topics_covered else ""
        user = f"""{phase_instr}{difficulty_line}{ja_line}

当前面试状态：
- 状态: {state}
- 已完成主题题数: {question_count}/{max_questions}
- 已用追问次数: {probe_count}/2（can_probe={can_probe}）
- 面试类型: {interview_type}
- 面试模式: {interview_mode}
- 激活维度: {', '.join(active_dimensions)}{exclusion}

候选人画像：
{profile_text}

{"本轮评估触发追问，原因：" + (probe_reason or "回答不够具体") if is_probe_triggered else "本轮评估未触发追问"}

最近对话：
{msgs_text}

请决定下一步："""
    else:
        ja_text = _job_analysis_text_en(ja)
        ja_line = f"\n\n{ja_text}" if ja_text else ""
        exclusion = f"\nTopics already covered (do NOT repeat): {', '.join(topics_covered)}" if topics_covered else ""
        user = f"""{phase_instr}{difficulty_line}{ja_line}

Current interview state:
- State: {state}
- Main questions completed: {question_count}/{max_questions}
- Probes used: {probe_count}/2 (can_probe={can_probe})
- Interview type: {interview_type}
- Interview mode: {interview_mode}
- Active dimensions: {', '.join(active_dimensions)}{exclusion}

Candidate profile:
{profile_text}

{"This round triggered a probe. Reason: " + (probe_reason or "Answer lacked specifics") if is_probe_triggered else "This round did NOT trigger a probe"}

Recent conversation:
{msgs_text}

Decide the next action:"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
