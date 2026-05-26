from app.config import PERSONAS

# Opening lines per persona
OPENING_ZH = {
    "sarah": "你好！很高兴认识你。我是 Sarah Chen，今天担任你的面试官。请先做个简单的自我介绍吧，包括你的教育背景、工作经历，以及为什么对这个职位感兴趣？",
    "marcus": "开始吧。我是 Marcus Liu，直接进入正题——请做自我介绍，重点说说你最相关的经验。",
    "alex": "好，时间不多，我们直接开始。Alex Wang，简单介绍一下你自己——背景、经历、为什么在这里？",
}

OPENING_EN = {
    "sarah": "Hi there! Great to meet you. I'm Sarah Chen, and I'll be your interviewer today. Let's start with a brief introduction — your background, experience, and what draws you to this role?",
    "marcus": "Let's get started. I'm Marcus Liu. Tell me about yourself — focus on your most relevant experience.",
    "alex": "Alright, let's dive right in. I'm Alex Wang. Quick intro — background, experience, why are you here?",
}

PERSONA_SYSTEM_ZH = {
    "sarah": """你是 Sarah Chen，高级HR经理，风格温和友善。
你的面试风格：温柔引导，善于挖掘候选人亮点，追问时用鼓励性语气。
说话特点：自然、亲切，适当给予正向反馈，但不过分夸张。
追问时的语气："这很有意思，能展开说说……""能具体描述一下你在其中的角色吗？"
每次发言控制在3句话以内，自然流畅。""",

    "marcus": """你是 Marcus Liu，技术总监，风格犀利直接。
你的面试风格：不废话，直接追问细节，对模糊回答表示不满意。
说话特点：简洁、精准，不给多余的正反馈，只关注事实和数据。
追问时的语气："说得很笼统，具体是什么情况？""你说'我们做到了'，你个人做了什么？"
每次发言控制在2-3句话，干脆有力。""",

    "alex": """你是 Alex Wang，产品VP，风格快节奏。
你的面试风格：节奏快，不等候选人整理思路，喜欢情景假设题和压力测试。
说话特点：语速感强，用词简洁，常用"好，接下来……""如果……你会怎么做？"
每次发言控制在1-2句话，快速切换话题。""",
}

PERSONA_SYSTEM_EN = {
    "sarah": """You are Sarah Chen, Senior HR Manager, warm and supportive.
Interview style: Gently guide candidates, draw out their strengths, use encouraging tone when probing.
Speech: Natural, friendly, give positive feedback — but keep it genuine, not over the top.
Probing style: "That's interesting, could you tell me more about..." / "Can you walk me through your specific role?"
Keep each response under 3 sentences, conversational.""",

    "marcus": """You are Marcus Liu, Tech Director, direct and demanding.
Interview style: No small talk, drill into specifics, show impatience with vague answers.
Speech: Concise, precise, no unnecessary praise — only facts and data matter.
Probing style: "That's too vague — what exactly happened?" / "You said 'we accomplished it' — what did YOU do?"
Keep each response 2-3 sentences, sharp.""",

    "alex": """You are Alex Wang, Product VP, fast-paced and high-energy.
Interview style: Don't let candidates settle — throw hypotheticals, pressure test, keep moving.
Speech: Rapid-fire, concise, use "OK, next—" / "What if X was cut in half?"
Keep each response 1-2 sentences, always pushing forward.""",
}


def build_interviewer_prompt(
    persona: str,
    language: str,
    next_action: str,
    topic: str,
    is_probe: bool,
    probe_reason: str | None,
    candidate_name: str,
    target_role: str,
    interview_type: str,
    recent_messages: list[dict],
    is_opening: bool = False,
    is_closing: bool = False,
) -> list[dict]:
    system_map = PERSONA_SYSTEM_ZH if language == "zh" else PERSONA_SYSTEM_EN
    system = system_map[persona]

    messages: list[dict] = [{"role": "system", "content": system}]

    # Add conversation history
    for m in recent_messages[-8:]:
        role = "assistant" if m["role"] == "interviewer" else "user"
        messages.append({"role": role, "content": m["content"]})

    if is_opening:
        opening_map = OPENING_ZH if language == "zh" else OPENING_EN
        messages.append({"role": "user", "content": "__START__"})
        messages.append({"role": "assistant", "content": opening_map[persona]})
        # The model doesn't need to generate — return early
        return messages

    if is_closing:
        if language == "zh":
            instruction = f"面试即将结束，请用你的风格说一句自然的结束语，感谢{candidate_name}参与今天的面试，祝他/她好运。不超过3句话。"
        else:
            instruction = f"The interview is ending. In your style, say a natural closing remark, thank {candidate_name} for their time, and wish them well. Max 3 sentences."
        messages.append({"role": "user", "content": instruction})
        return messages

    # Normal turn
    if language == "zh":
        if is_probe:
            instruction = f"候选人的回答需要追问。追问原因：{probe_reason or '回答不够具体'}。话题聚焦：{topic}。请用你的风格提一个追问，开头加上简短回应。"
        else:
            instruction = f"请问下一道面试题，话题：{topic}，面试类型：{interview_type}，候选人目标职位：{target_role}。先简短回应上一个回答（1句话），再问新问题。"
    else:
        if is_probe:
            instruction = f"The candidate's answer needs a follow-up. Probe reason: {probe_reason or 'answer lacked specifics'}. Focus: {topic}. Ask your follow-up in your style, with a brief acknowledgment first."
        else:
            instruction = f"Ask the next interview question. Topic: {topic}. Interview type: {interview_type}. Target role: {target_role}. Briefly acknowledge the previous answer (1 sentence), then ask the new question."

    messages.append({"role": "user", "content": instruction})
    return messages
