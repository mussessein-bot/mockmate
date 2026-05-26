STRATEGY_SYSTEM_ZH = """你是面试策略规划师。根据当前面试进度和评估结果，决定下一步行动。

输出严格的 JSON，格式如下：
{
  "next_action": "continue" | "probe" | "close",
  "topic": "下一个话题的简短描述（如果 next_action 是 probe，填写追问关注点）",
  "dimension_focus": ["维度key1", "维度key2"],
  "reasoning": "一句话说明原因"
}

规则：
- "probe": 只有 can_probe=true 时才能选，is_probe_triggered=true 时优先选
- "close": 动态模式下，当主题题数 >= 6 且候选人能力已基本评估完毕时选择；预设模式禁止选 close
- "continue": 继续下一道正式题
- dimension_focus 从当前激活维度中选1-2个重点关注
- topic 要具体，给面试官明确的方向（如"带团队解决冲突的经历"而不是"领导力"）
- 动态模式下，若题数已达到12题，必须选 close"""

STRATEGY_SYSTEM_EN = """You are an interview strategy planner. Based on the current interview progress and evaluation, decide the next action.

Output strict JSON only:
{
  "next_action": "continue" | "probe" | "close",
  "topic": "Brief description of the next topic (if probing, describe the follow-up focus)",
  "dimension_focus": ["dimension_key1", "dimension_key2"],
  "reasoning": "One sentence explanation"
}

Rules:
- "probe": Only when can_probe=true; prioritize when is_probe_triggered=true
- "close": Dynamic mode only — when main questions >= 6 and the candidate's abilities are sufficiently assessed. Forbidden in preset mode. MUST choose close when question_count >= 12.
- "continue": Move to the next main question
- dimension_focus: Pick 1-2 keys from active_dimensions to focus on
- topic: Be specific — give the interviewer clear direction"""


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
    recent_messages: list[dict],  # last few Q&A pairs
    language: str,
) -> list[dict]:
    system = STRATEGY_SYSTEM_ZH if language == "zh" else STRATEGY_SYSTEM_EN

    msgs_text = "\n".join(
        f"[{m['role']}]: {m['content'][:200]}" for m in recent_messages[-6:]
    )

    if language == "zh":
        user = f"""当前面试状态：
- 状态: {state}
- 已完成主题题数: {question_count}/{max_questions}
- 已用追问次数: {probe_count}/2（can_probe={can_probe}）
- 面试类型: {interview_type}
- 面试模式: {interview_mode}
- 激活维度: {', '.join(active_dimensions)}

候选人画像：
{profile_text}

{"本轮评估触发追问，原因：" + (probe_reason or "回答不够具体") if is_probe_triggered else "本轮评估未触发追问"}

最近对话：
{msgs_text}

请决定下一步："""
    else:
        user = f"""Current interview state:
- State: {state}
- Main questions completed: {question_count}/{max_questions}
- Probes used: {probe_count}/2 (can_probe={can_probe})
- Interview type: {interview_type}
- Interview mode: {interview_mode}
- Active dimensions: {', '.join(active_dimensions)}

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
