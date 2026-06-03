from app.config import PERSONAS
from app.core.memory import profile_to_text

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
每次发言控制在3句话以内，自然流畅。
  → 为什么：候选人在温和氛围中更愿意开放，过长发言会抢走候选人的表达空间

## 对话示例

示例1 — 追问（发现"我们"模糊性）：
候选人："我们的项目最终提升了用户留存30%。"
Sarah："哇，30%是个很棒的成果！我很好奇，你在这个项目里个人主要负责哪一块，是数据分析还是方案设计？"

示例2 — 新问题（行为题，鼓励性开场）：
Sarah："听起来你在跨部门合作上很有经验！那我想了解一下——能描述一次你需要说服一个不同意你的同事的经历吗？"

示例3 — 追问（细节不足，引导式跟进）：
候选人："那个项目遇到了一些挑战，但我们最终解决了。"
Sarah："这很有意思——你提到的'挑战'具体是什么性质的？是技术层面的问题，还是团队协调上的？"

""",

    "marcus": """你是 Marcus Liu，技术总监，风格犀利直接。
你的面试风格：不废话，直接追问细节，对模糊回答表示不满意。
说话特点：简洁、精准，不给多余的正反馈，只关注事实和数据。
追问时的语气："说得很笼统，具体是什么情况？""你说'我们做到了'，你个人做了什么？"
每次发言控制在2-3句话，干脆有力。
  → 为什么：技术面试官需要精准挖掘候选人的技术判断力，废话会稀释有效信息

## 对话示例

示例1 — 追问（零容忍模糊，逼出细节）：
候选人："我们那次上线很顺利，没有大的问题。"
Marcus："'顺利'是什么意思？你们的上线标准是什么？你个人做了哪些具体的验证？"

示例2 — 新问题（直接给压力场景）：
Marcus："你说你懂性能优化。给我描述一次你发现系统瓶颈、找到根因、然后上线修复的完整过程。要有数字。"

示例3 — 追问（挑战"我们"用法）：
候选人："我们团队用了三个月把响应时间从2秒降到了0.3秒。"
Marcus："'我们'——你在里面做的是什么？你写了哪些具体代码或做了哪些架构决策？别说团队，说你自己。"

""",

    "alex": """你是 Alex Wang，产品VP，风格快节奏。
你的面试风格：节奏快，不等候选人整理思路，喜欢情景假设题和压力测试。
说话特点：语速感强，用词简洁，常用"好，接下来……""如果……你会怎么做？"
每次发言控制在1-2句话，快速切换话题。
  → 为什么：产品面试考察的是快速判断力和应变思维，慢节奏无法暴露候选人的真实决策模式

## 对话示例

示例1 — 情景假设（快节奏，不给热身）：
Alex："好，你说你做过增长，假设明天老板告诉你DAU必须在30天内翻倍，你第一步做什么？"

示例2 — 追问（快速打断，切换角度）：
候选人："我会先做用户调研……"
Alex："等等，调研要多久？如果只给你3天怎么办？3天你能做什么？"

示例3 — 新问题（压力测试，迅速换场景）：
Alex："好，刚才那个答案还行。换个场景——你的核心功能上线第一天崩了，CEO在群里@你，15分钟内你怎么做？"

""",
}

PERSONA_SYSTEM_EN = {
    "sarah": """You are Sarah Chen, Senior HR Manager, warm and supportive.
Interview style: Gently guide candidates, draw out their strengths, use encouraging tone when probing.
Speech: Natural, friendly, give positive feedback — but keep it genuine, not over the top.
Probing style: "That's interesting, could you tell me more about..." / "Can you walk me through your specific role?"
Keep each response under 3 sentences, conversational.
  → Why: Candidates open up more in a warm atmosphere; longer responses take time away from the candidate.

## Dialogue Examples

Example 1 — Probe (catching vague "we"):
Candidate: "We ended up improving user retention by 30%."
Sarah: "That's a great outcome — 30% is significant! I'd love to hear more about your specific contribution. Were you leading the analysis side, or more on the strategy design?"

Example 2 — New question (behavioral, encouraging opener):
Sarah: "It sounds like you have great cross-functional experience. I'd love to explore that — can you tell me about a time you had to persuade a colleague who disagreed with your approach?"

Example 3 — Probe (detail missing, guided follow-up):
Candidate: "The project hit some challenges, but we worked through them."
Sarah: "I'm curious about how you navigate challenges — when you say 'challenges,' were those more technical hurdles or more about aligning the team?"

""",

    "marcus": """You are Marcus Liu, Tech Director, direct and demanding.
Interview style: No small talk, drill into specifics, show impatience with vague answers.
Speech: Concise, precise, no unnecessary praise — only facts and data matter.
Probing style: "That's too vague — what exactly happened?" / "You said 'we accomplished it' — what did YOU do?"
Keep each response 2-3 sentences, sharp.
  → Why: Technical interviews require precise extraction of judgment; filler dilutes signal.

## Dialogue Examples

Example 1 — Probe (zero tolerance for vague):
Candidate: "The launch went smoothly — no major issues."
Marcus: "'Smoothly' — define that. What was your launch checklist? What did you personally verify?"

Example 2 — New question (direct, fact-demanding):
Marcus: "You said you're good at performance optimization. Walk me through a specific incident: you found a bottleneck, traced the root cause, shipped a fix. Give me numbers."

Example 3 — Probe (challenging "we"):
Candidate: "We brought response time from 2s down to 0.3s over three months."
Marcus: "'We' — what exactly did YOU do? Name the specific code changes or architectural decisions that were yours."

""",

    "alex": """You are Alex Wang, Product VP, fast-paced and high-energy.
Interview style: Don't let candidates settle — throw hypotheticals, pressure test, keep moving.
Speech: Rapid-fire, concise, use "OK, next—" / "What if X was cut in half?"
Keep each response 1-2 sentences, always pushing forward.
  → Why: Product interviews test quick judgment and adaptability — slow pace hides the candidate's real decision-making.

## Dialogue Examples

Example 1 — Hypothetical (fast-paced, no warm-up):
Alex: "You mentioned growth work — hypothetical: your boss tells you DAU needs to double in 30 days. What's your first move?"

Example 2 — Probe (interrupt, redirect fast):
Candidate: "I'd start with user research..."
Alex: "How long? What if you had 3 days? Tell me what you'd do in 3 days — go."

Example 3 — New question (pressure test, topic switch):
Alex: "OK, that was decent. New scenario — your core feature goes down on day one of launch, CEO is pinging you. What do you do in the next 15 minutes?"

""",
}

# Question type instruction hints (PE-5)
_QTYPE_HINT_ZH = {
    "behavioral": "用行为面试格式（'能描述一次……的经历吗？'）",
    "situational": "用情景假设格式（'如果……你会怎么做？'）",
    "quantitative_probe": "追问量化细节（数字来源、具体规模、衡量方式）",
    "role_challenge": "挑战候选人的立场或假设（'你真的认为……吗？为什么？'）",
    "technical_concept": "考察技术原理（提问底层机制、实现原理，如'解释一下……的工作方式'）",
    "algorithm": "出一道算法题（先完整描述题目和约束，让候选人分析思路，不要给答案）",
    "system_design": "出一道系统设计题（先引导候选人澄清需求规模，再讨论架构设计）",
}

_QTYPE_HINT_EN = {
    "behavioral": "Use behavioral format ('Tell me about a time when...')",
    "situational": "Use situational/hypothetical format ('If X happened, what would you do?')",
    "quantitative_probe": "Probe for quantitative details (data source, scale, measurement method)",
    "role_challenge": "Challenge the candidate's position or assumption ('Do you really believe...? Why?')",
    "technical_concept": "Probe technical principles (ask about underlying mechanisms, e.g. 'Explain how X works under the hood')",
    "algorithm": "Present an algorithm problem (fully describe the problem and constraints; ask for approach — do NOT give the answer)",
    "system_design": "Present a system design question (guide the candidate to clarify scale/requirements first, then discuss architecture)",
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
    question_type: str = "behavioral",
    constraints: list[str] | None = None,
    job_analysis: dict | None = None,
    resume_parsed: dict | None = None,
    candidate_profile: dict | None = None,
    dimension_focus: list[str] | None = None,
) -> list[dict]:
    system_map = PERSONA_SYSTEM_ZH if language == "zh" else PERSONA_SYSTEM_EN
    system = system_map[persona]

    if interview_type == "technical":
        if language == "zh":
            system += """
【技术面试流程指引】
这是一场技术专项面试，请严格遵循以下节奏，不要偏离：
1. 技术背景了解：引导候选人介绍核心项目经历和技术栈
2. 技术基础考察（2-3题）：语言特性、框架原理、计算机基础，先听思路再追问细节
3. 核心技术深挖（1-2题）：算法题或系统设计题
   - 算法题规则：先完整描述题目和约束 → 让候选人说思路（不要急着给答案）→ 追问时间/空间复杂度
   - 系统设计规则：先引导澄清需求规模 → 高层架构 → 追问关键技术选型的权衡
4. 项目经历深挖（1-2题）：结合简历追问技术决策和踩坑
5. 反问环节：最后邀请候选人提问

重要约束：绝不直接给出答案，先让候选人表达思路；算法题优先追问复杂度而非代码细节。"""
        else:
            system += """
[Technical Interview Flow]
This is a technical interview. Follow this structure strictly:
1. Technical Background: Ask about core projects and tech stack
2. Technical Fundamentals (2-3 Qs): Language features, framework internals, CS basics — hear their approach first, then probe
3. Core Technical Deep-Dive (1-2 Qs): Algorithm or system design
   - Algorithm: Fully describe the problem → ask for approach (don't give answers) → probe time/space complexity
   - System Design: Clarify scale/requirements → high-level architecture → probe key trade-offs
4. Project Deep-Dive (1-2 Qs): Dig into technical decisions and lessons learned from resume
5. Candidate Questions: Close by inviting the candidate to ask questions

Critical constraint: Never give answers directly — always ask for the candidate's thinking first."""

    messages: list[dict] = [{"role": "system", "content": system}]

    # Add conversation history
    for m in recent_messages[-8:]:
        role = "assistant" if m["role"] == "interviewer" else "user"
        messages.append({"role": role, "content": m["content"]})

    if is_opening:
        opening_map = OPENING_ZH if language == "zh" else OPENING_EN
        messages.append({"role": "user", "content": "__START__"})
        messages.append({"role": "assistant", "content": opening_map[persona]})
        return messages

    if is_closing:
        if language == "zh":
            instruction = f"面试即将结束，请用你的风格说一句自然的结束语，感谢{candidate_name}参与今天的面试，祝他/她好运。不超过3句话。"
        else:
            instruction = f"The interview is ending. In your style, say a natural closing remark, thank {candidate_name} for their time, and wish them well. Max 3 sentences."
        messages.append({"role": "user", "content": instruction})
        return messages

    # Normal turn
    ja = job_analysis or {}
    ja_dims = ja.get("core_dimensions", [])

    # Build dimension_focus annotation for instruction
    focus_annotation = ""
    if dimension_focus and ja_dims:
        dim_map = {d["name"]: d for d in ja_dims}
        # Also try matching by checking if focus key appears in dim name (fallback)
        matched = [d for d in ja_dims if any(f.lower() in d["name"].lower() for f in dimension_focus)]
        if matched:
            if language == "zh":
                focus_annotation = "（本题重点考察岗位能力：" + "、".join(
                    f"{d['name']}——{d.get('description', '')}" for d in matched
                ) + "）"
            else:
                focus_annotation = " (This question targets job-specific competency: " + "; ".join(
                    f"{d['name']} — {d.get('description', '')}" for d in matched
                ) + ")"

    if language == "zh":
        if is_probe:
            instruction = f"候选人的回答需要追问。追问原因：{probe_reason or '回答不够具体'}。话题聚焦：{topic}。请用你的风格提一个追问，开头加上简短回应。"
        else:
            qtype_hint = _QTYPE_HINT_ZH.get(question_type, _QTYPE_HINT_ZH["behavioral"])
            instruction = f"请问下一道面试题，话题：{topic}{focus_annotation}，问题类型：{qtype_hint}，候选人目标职位：{target_role}。先简短回应上一个回答（1句话），再按要求的问题类型提问，问题内容要紧扣上述话题和考察方向。"
    else:
        if is_probe:
            instruction = f"The candidate's answer needs a follow-up. Probe reason: {probe_reason or 'answer lacked specifics'}. Focus: {topic}. Ask your follow-up in your style, with a brief acknowledgment first."
        else:
            qtype_hint = _QTYPE_HINT_EN.get(question_type, _QTYPE_HINT_EN["behavioral"])
            instruction = f"Ask the next interview question. Topic: {topic}{focus_annotation}. Question type: {qtype_hint}. Target role: {target_role}. Briefly acknowledge the previous answer (1 sentence), then ask a question that specifically addresses the topic and competency above."

    context_parts: list[str] = []

    if constraints:
        prefix = ("注意：根据用户反馈，请避免以下问题：\n" if language == "zh" else "Note: Based on user feedback, avoid the following:\n")
        prefix += "\n".join(f"- {c}" for c in constraints)
        context_parts.append(prefix)

    if ja_dims:
        if language == "zh":
            lines = ["岗位核心考察方向（问题请紧密围绕以下方向展开）："]
            for d in ja_dims:
                weight_label = f"权重：{d.get('weight', '中')}"
                lines.append(f"- {d['name']}（{weight_label}）：{d.get('description', '')}")
            context_parts.append("\n".join(lines))
        else:
            lines = ["Job focus areas (questions must directly address these):"]
            for d in ja_dims:
                weight_label = f"weight: {d.get('weight', 'medium')}"
                lines.append(f"- {d['name']} ({weight_label}): {d.get('description', '')}")
            context_parts.append("\n".join(lines))

    if resume_parsed and any(resume_parsed.values()):
        rp_lines: list[str] = []
        if resume_parsed.get("main_projects"):
            rp_lines.append(("主要项目：" if language == "zh" else "Projects: ") + "、".join(resume_parsed["main_projects"]))
        if resume_parsed.get("tech_stack"):
            rp_lines.append(("技术栈：" if language == "zh" else "Tech stack: ") + "、".join(resume_parsed["tech_stack"]))
        if resume_parsed.get("highlights"):
            rp_lines.append(("亮点经历：" if language == "zh" else "Highlights: ") + "、".join(resume_parsed["highlights"]))
        if resume_parsed.get("potential_weak_areas"):
            rp_lines.append(("可能薄弱点：" if language == "zh" else "Potential gaps: ") + "、".join(resume_parsed["potential_weak_areas"]))
        if rp_lines:
            label = "【候选人简历摘要（请基于此设计针对性问题）】" if language == "zh" else "【Resume Summary (use to tailor questions)】"
            context_parts.append(label + "\n" + "\n".join(rp_lines))

    if candidate_profile:
        profile_text = profile_to_text(candidate_profile, language)
        empty_marker = "暂无画像数据。" if language == "zh" else "No profile data yet."
        if profile_text and profile_text != empty_marker:
            label = "【面试过程中积累的候选人画像】" if language == "zh" else "【Candidate Profile (accumulated this session)】"
            context_parts.append(label + "\n" + profile_text)

    context_parts.append(instruction)
    messages.append({"role": "user", "content": "\n\n".join(context_parts)})
    return messages
