# MockMate 论文规划与系统改进路线图

> 本文档记录了 MockMate AI 模拟面试系统的论文框架、所有待实现改进项，以及技术方向的详细说明。
> 供后续 agent 或团队成员接力推进使用。

---

## 一、论文框架

### 题目（建议）

**《基于多智能体架构的 AI 模拟面试系统：提示工程、记忆机制与检索增强的协同设计》**

### 五大技术方向

1. Prompt Engineering（提示工程）
2. Multi-Agent Orchestration（多智能体编排）
3. Memory Systems（记忆系统）
4. RAG（检索增强生成）
5. LLM-as-Judge（大模型自动评估）

---

### 第一章：引言

- 研究背景：求职市场竞争激烈，面试准备缺乏高质量、个性化的工具
- 现有问题：静态题库缺乏交互，人工 mock 成本高，通用 AI 聊天工具无专项面试逻辑
- 核心挑战：单一 LLM 同时承担评估、决策、生成三个角色时存在角色冲突和注意力分散
- 论文贡献：提出五层技术协同架构，实现针对特定公司和岗位的个性化、可靠的模拟面试

---

### 第二章：系统架构总览

#### 整体流程

```
用户设置（公司/岗位/简历/JD）
    ↓
会话创建（简历解析、维度初始化）
    ↓
面试循环：
  候选人回答 → EvaluatorAgent → StrategyAgent → InterviewerAgent → 生成下一题
    ↓
面试结束 → FeedbackAgent（逐句标注 + 参考答案 + 雷达图）
```

#### 三 Agent 流水线


| Agent            | 职责             | 输入                  | 输出                       |
| ---------------- | -------------- | ------------------- | ------------------------ |
| EvaluatorAgent   | 评估回答质量，更新候选人画像 | 问题 + 回答 + 维度        | 评分 JSON + 是否追问           |
| StrategyAgent    | 决策下一步行动        | 评估结果 + 面试进度         | probe / continue / close |
| InterviewerAgent | 生成面试官回应        | 动作指令 + 候选人画像 + 对话历史 | 自然语言问题                   |


#### 状态机

```
INIT → OPENING → BEHAVIORAL ⇄ DEEP_DIVE → TECHNICAL → CLOSING → COMPLETED
```

#### 技术栈

- 后端：FastAPI + Python + DeepSeek-V3（via Ark API）
- 前端：Next.js + TypeScript + Tailwind CSS + Recharts
- 语音：火山引擎 TTS/STT
- 存储：SQLite + aiosqlite

---

### 第三章：Prompt Engineering（提示工程）

**核心论点**：好的 prompt 设计让每个 agent 只做一件清晰的事，通过结构化约束、示例引导和动态合成，比单一大 prompt 更可靠、更可控。

#### 3.1 角色设定（Role Prompting）

当前实现：三种面试官 persona，每个有独立 system prompt。

**待改进**：加入 Few-shot Examples，用对话示例锚定风格。

现状（纯描述，效果不稳定）：

```
追问时的语气："这很有意思，能展开说说……"
```

改进后（描述 + 示例，风格一致性更高）：

```
追问示例：
候选人说："我们团队做了一个推荐系统，效果很好。"
Sarah 的追问："听起来很有成就感！你在这个推荐系统里具体负责哪一块，是算法侧还是工程侧？"

候选人说："我处理过很多复杂的客户问题。"
Sarah 的追问："能给我讲一个最棘手的案例吗？当时是什么情况？"
```

**实现位置**：`backend/app/llm/prompts/interviewer_prompts.py` → `PERSONA_SYSTEM_ZH/EN`

#### 3.2 Chain of Thought（CoT）in Evaluator

当前问题：evaluator 直接输出分数 JSON，没有推理过程，评分一致性差。

改进：先推理，再评分。

```
请按以下步骤评估：
1. 这个回答展示了哪些具体内容？
2. 哪里有细节支撑，哪里模糊泛化？
3. 候选人是否明确了自己在团队中的角色？
4. 基于以上分析，各维度评分为……
```

**实现位置**：`backend/app/llm/prompts/evaluator_prompts.py` → `EVALUATOR_SYSTEM_ZH/EN`

**可做实验**：同一组回答，有/无 CoT 各评估 5 次，计算 Kappa 一致性系数。

#### 3.3 Self-Critique（自我批判）——参考答案两轮生成

当前问题：`_model_answer` 一次生成，质量依赖随机性，经常产出"情境：xxx\n任务：xxx"的模板式答案。

改进：两轮生成。

```
第一轮：以求职者第一人称，生成一个口语化的面试回答草稿（200字）
第二轮：检查这个草稿：
  - 是否包含量化数据？没有则补充
  - 是否用"我们"但没说自己的角色？有则修正
  - 是否有超过2句废话开场？有则删除
  输出改进后的最终版本，语气要自然流畅，不要显式写"情境/任务/行动/结果"标题
```

同时传入 `dimension_focus`，让答案有意识地优化评分维度。

**实现位置**：`backend/app/api/feedback.py` → `_model_answer()` 函数

temperature 从 0.5 提升至 0.7。

#### 3.4 动态 Prompt 合成（按面试阶段）

当前问题：strategy prompt 的指令是静态的，不随面试进度变化。

改进：根据当前阶段注入不同侧重的指令。

```python
if question_count <= 2:
    phase_instruction = "面试刚开始，优先选宽泛话题摸底，不要过早追问细节"
elif question_count >= max_questions - 2:
    phase_instruction = "面试即将结束，聚焦候选人最薄弱的1-2个维度做最后确认"
else:
    phase_instruction = "深入挖掘候选人画像中的薄弱项，避免重复已覆盖的话题"
```

**实现位置**：`backend/app/llm/prompts/strategy_prompts.py` → `build_strategy_prompt()`

#### 3.5 问题类型多样化

当前问题：全部是开放式行为题，一场面试 8 道题结构相同，体验单调。

改进：strategy agent 决定题型，interviewer 按题型出题。

题型分类：

- **行为题**（默认）：Tell me about a time...
- **情景假设题**：如果你面对 X 情况，你会怎么做？
- **量化追问**：你之前提到"提升了效率"，具体数字是多少，怎么衡量？
- **反角色题**（Marcus/Alex 人设专用）：你刚才说"我们做到了"，你个人做了什么？

**实现位置**：`strategy_prompts.py` 加 `question_type` 字段；`interviewer_prompts.py` 按 `question_type` 调整 instruction

#### 3.6 自适应难度

根据候选人历史得分动态调整题目难度。

```python
recent_avg = average(last_3_question_scores)
if recent_avg >= 8.0:
    difficulty_instruction = "候选人表现优秀，提高难度：问更抽象的场景、更极端的假设"
elif recent_avg <= 5.0:
    difficulty_instruction = "候选人表现偏弱，换方向：用更具体的引导式问题帮助候选人展开"
```

**实现位置**：`build_strategy_prompt()` 加入历史得分参数

#### 3.7 Rule + Reason + Example 规则设计

当前 strategy prompt 的规则写法：

```
- "probe": 只有 can_probe=true 时才能选
```

改进写法：

```
- "probe"：只有 can_probe=true 时才能选。
  原因：连续追问打乱节奏，会让候选人感到被针对。
  反例：上一题已经是追问（last_was_probe=true），本题绝对不能选 probe。
```

LLM 理解"为什么"之后，边界情况的判断准确率更高。

**实现位置**：所有三个 `_SYSTEM_ZH/EN` prompt

---

### 第四章：Multi-Agent Orchestration（多智能体编排）

**核心论点**：面试任务本质上是多个子任务的组合，专门化的 agent 分工比单一大 agent 更可靠，同时需要设计人类介入机制保证可控性。

#### 4.1 任务分解原则

为什么不用单个 LLM 完成全部工作：

- 角色冲突：同一个模型既要"客观评分"又要"生成鼓励性追问"，目标相互干扰
- 注意力分散：context 中同时包含评分标准、对话历史、出题逻辑，LLM 容易混乱
- 可维护性：每个 agent 独立，可以单独调优

#### 4.2 Agent 通信协议设计

关键原则：上游输出的不确定性不传染给下游。

- EvaluatorAgent 输出严格 JSON（`is_probe_triggered: bool`, `probe_reason: str`）
- StrategyAgent 从 JSON 读取，输出三选一字符串（`probe/continue/close`）
- InterviewerAgent 收到具体 topic 字符串（"带团队处理线上故障"），而非抽象标签（"领导力"）

#### 4.3 Human-in-the-Loop（HITL）——用户纠正面试官

**背景**：用户在实际体验中发现面试官产生偏差（问错方向、重复话题、难度不对），但当前无法干预，只能重开面试。

**设计方案**：

后端新增端点：

```
POST /api/interview/{session_id}/correction
Body: { "message": "你问的这个问题不适合我面试的岗位，请换一个话题" }
```

处理逻辑：将用户纠正写入 `MessageRole.SYSTEM` 消息，注入对话历史，面试官下一轮自动看到并调整。

前端：面试界面加 ⚙️ 按钮，点击展开纠正输入框，发送后显示为特殊样式气泡（区别于普通答案）。

**学术意义**：Human-in-the-Loop 是 agent 可控性研究的核心主题，对应"自主性 vs 可控性"的权衡。

**实现位置**：

- 后端：`backend/app/api/interview.py` 新增 `/correction` endpoint
- 前端：`frontend/app/interview/[sessionId]/page.tsx` 加纠正 UI

#### 4.4 状态机与 Agent 约束

状态机的作用是约束 agent 的决策空间，防止 LLM 自由发挥产生不合法的转移：

- `can_probe()` 限制追问次数（最多 2 次 / session）
- `last_was_probe` 防止连续追问
- `max_questions` 强制面试长度上限

这是 agent 系统中"硬约束"与"软约束（prompt）"结合的典型实践。

---

### 第五章：Memory Systems（记忆系统）

**核心论点**：面试 agent 需要多层记忆才能实现真正的个性化，不同层级的记忆服务于不同的决策需求。

#### 5.1 四种记忆类型的实现


| 记忆类型            | 定义                 | 当前系统中的实现                      | 改进方向         |
| --------------- | ------------------ | ----------------------------- | ------------ |
| Working Memory  | 当前任务的即时上下文         | 最近 8 条对话（滑动窗口）                | 窗口大小动态调整     |
| Episodic Memory | 具体事件的记录            | `evaluations` 列表，每题评估         | 无需改动         |
| Semantic Memory | 从 episodic 提炼的抽象知识 | `candidate_profile_json`，实时更新 | 注入面试官 prompt |
| External Memory | 会话外部的持久知识          | 简历文本（存储但未使用）、JD（待实现）          | 解析后结构化注入     |


#### 5.2 简历驱动个性化（改进 #5）

**当前问题**：`resume_text` 存储在 `CandidateProfile`，但面试官 prompt 完全没有使用，所有候选人面对相同质量的通用问题。

**改进方案**：

session 创建时调用一次 LLM 解析简历：

```python
async def parse_resume(resume_text: str) -> dict:
    prompt = """从以下简历中提取结构化信息，输出 JSON：
    {
      "main_projects": ["项目名：简介"],
      "tech_stack": ["技术1", "技术2"],
      "years_of_experience": 2,
      "highlights": ["最值得深挖的经历1", "最值得深挖的经历2"],
      "potential_weak_areas": ["可能的薄弱点"]
    }"""
```

将解析结果注入 interviewer prompt：

```
候选人背景摘要：
- 主要项目：XX（可以问"当时遇到的最大挑战是什么？"）
- 技术栈：Python, React, MySQL
- 亮点经历：曾主导跨部门项目协调
请基于以上背景，设计针对性问题。
```

**实现位置**：`backend/app/api/sessions.py`（session 创建时）+ `interviewer_prompts.py`

#### 5.3 JD 注入全链路（改进 #4）

**当前问题**：`CandidateProfile.target_company` 字段存在但前端没有输入入口；无 `job_description` 字段；三个 agent 的 prompt 都不知道岗位要求。

**改进方案**：

数据模型（`backend/app/core/models.py`）：

```python
class CandidateProfile(BaseModel):
    name: str
    target_role: str
    target_company: Optional[str] = None
    job_description: Optional[str] = None  # 新增
    resume_text: Optional[str] = None
    language: Language = Language.ZH
```

前端 Setup 页面（Step 1）新增：

- "目标公司"文本框（选填）
- "职位描述 / JD"大文本框（选填，粘贴招聘 JD）

JD 在 session 创建时提炼关键词，注入三个 agent：

- **Interviewer**：问题要围绕岗位核心要求
- **Strategy**：话题选择优先 JD 高频考察点
- **Evaluator**：评估时参考岗位要求作为标准

#### 5.4 candidate_profile_json 跨 Agent 共享（改进 #12）

**当前问题**：EvaluatorAgent 持续更新候选人画像（薄弱项、已提技能、覆盖话题），但 InterviewerAgent 完全看不到这个画像，无法做到"我知道你之前提到过 XX"。

**改进**：在 `build_interviewer_prompt()` 中加入候选人画像摘要：

```
当前候选人画像（面试过程中积累）：
- 已覆盖话题：团队协作、项目管理
- 观察到的优点：表达清晰，善用数据
- 薄弱项：缺少量化结果，角色不够清晰
- 值得深挖的关键词：曾提到"复杂的技术决策"但未展开
```

**实现位置**：`backend/app/llm/prompts/interviewer_prompts.py` → `build_interviewer_prompt()` 加 `candidate_profile` 参数

---

### 第六章：RAG（检索增强生成）

**核心论点**：技术专项面试不能完全依赖 LLM 凭空生成，行为题 LLM 够用，技术题必须有题库支撑以保证专业性、减少幻觉。

#### 6.1 为什么技术面试必须用 RAG


| 对比维度     | 行为面试          | 技术专项面试                |
| -------- | ------------- | --------------------- |
| 问题套路     | 相对固定（STAR 框架） | 领域差异巨大（前端/后端/算法/系统设计） |
| LLM 生成质量 | 方差小，质量稳定      | 方差大，容易幻觉              |
| 题目验证难度   | 软技能，难以验证对错    | 技术细节，答案有明确对错          |
| 需要题库     | 可选            | **必须**                |


#### 6.2 题库结构设计

```json
{
  "id": "fe_001",
  "question": "解释一下 React 中 useEffect 的依赖数组的作用，以及为空数组时的行为",
  "direction": "frontend",
  "difficulty": 2,
  "dimensions": ["tech_depth", "logic"],
  "tags": ["react", "hooks", "lifecycle"],
  "model_answer": "useEffect 的依赖数组控制 effect 的执行时机……",
  "common_probes": [
    "如果不传依赖数组会怎样？",
    "cleanup function 什么时候执行？",
    "为什么不能在 useEffect 里直接用 async 函数？"
  ],
  "difficulty_variants": {
    "easy": "解释 useState 和 useEffect 各自的作用",
    "hard": "useEffect 与 useLayoutEffect 的区别，什么场景必须用 useLayoutEffect？"
  }
}
```

技术方向分类：

- `frontend`：React, CSS, 浏览器原理, 性能优化
- `backend`：数据库, API 设计, 缓存, 分布式
- `algorithm`：数据结构, 复杂度分析, 常见算法
- `system_design`：系统架构, 高可用, 微服务
- `data`：SQL, 数据分析, 统计基础

每个方向初始建 50-100 题，每题含难度变体。

#### 6.3 检索流程

```
用户输入 target_role + 简历关键词
    ↓
向量化 → 在题库中检索 top-3 相关题目
    ↓
LLM 根据候选人背景改写措辞（不直接照搬）
    ↓
InterviewerAgent 以改写后的题目为基础出题
```

检索策略：

- 初期：TF-IDF 关键词匹配（实现简单）
- 进阶：sentence-transformers 向量相似度（质量更高）

#### 6.4 幻觉消除对比实验

实验设计：

- 对照组：纯 LLM 生成技术题（当前方案）
- 实验组：RAG 检索 + LLM 改写

评估指标：

- 技术细节准确率（人工标注）
- 题目重复率
- 候选人主观评分（题目专业感）

---

### 第七章：LLM-as-Judge（大模型自动评估）

**核心论点**：用 LLM 评估面试回答是否可靠？如何通过评估 prompt 设计和输出结构提升一致性，并将评估结果转化为对候选人真正有价值的学习反馈。

#### 7.1 LLM-as-Judge 的偏见来源与缓解


| 偏见类型  | 描述          | 缓解方式                      |
| ----- | ----------- | ------------------------- |
| 长度偏见  | 更长的回答得分更高   | 评分标准明确限定"具体性"而非"完整性"      |
| 自我偏好  | 偏向自己风格的回答   | 明确评分维度，减少主观自由度            |
| 位置偏见  | 对话末尾的信息权重更高 | 要求模型先读完再评分（CoT）           |
| 一致性问题 | 同一回答多次评分差异大 | temperature 降低，加 CoT 强制推理 |


#### 7.2 CoT 评分 vs 直接评分

改进后的 evaluator prompt：

```
请按以下步骤评估（不要跳过步骤）：

【分析】
1. 候选人的回答展示了哪些具体内容？
2. 是否有量化数据支撑？
3. 候选人是否清晰说明了自己的角色（避免"我们"而不说个人贡献）？
4. 回答结构是否清晰（有情境、有行动、有结果）？

【评分】
基于以上分析，输出 JSON……
```

#### 7.3 面试复盘逐句标注（改进 #8）

**当前问题**：feedback 只有总分和维度雷达图，候选人不知道自己哪句话失分、哪句话得分。

**改进方案**：

finalize 时新增一次 LLM call：

```python
async def _annotate_answer(question: str, answer: str, dimensions: list[str]) -> list[dict]:
    prompt = f"""对以下面试回答进行逐句分析，输出 JSON 数组：
    [
      {{"sentence": "原文句子", "label": "good/weak/neutral", "reason": "评价理由", "suggestion": "改进建议（仅 weak 时填写）"}}
    ]

    问题：{question}
    回答：{answer}
    评分维度：{dimensions}
    """
```

前端渲染：

- `good` 句子：绿色高亮
- `weak` 句子：黄色高亮 + hover 显示改进建议
- `neutral` 句子：无特殊样式

**实现位置**：`backend/app/api/feedback.py` + `frontend/app/feedback/[sessionId]/page.tsx`

#### 7.4 参考答案 vs 用户答案差异分析（改进 #10）

**当前问题**：参考答案和用户答案完全割裂，候选人需要自己对比，找不到重点。

**改进**：finalize 时将两者一起传给 LLM 做差异分析：

```python
prompt = f"""
用户的实际回答：{user_answer}
示范参考答案：{model_answer}

请指出用户回答与示范答案的主要差距（3条以内），格式：
[
  {{"gap": "缺少量化数据", "example": "示范答案中说'提升了30%'，用户只说'效果很好'"，"suggestion": "在结果描述后加上具体数字"}}
]
"""
```

#### 7.5 实时评分显示（改进 #15）

文字模式下，每道题回答发送后，在界面右侧即时展示：

- 各维度得分条（动画展开）
- 一句话 feedback
- 是否触发追问的提示

这让用户在面试过程中实时感知自己的表现，而不是等到结束才看到反馈。

**实现位置**：`respond` API 已返回 `evaluation` 字段，前端在 text mode 下展示即可。

#### 7.6 可做实验

**实验 A：评分一致性（inter-rater reliability）**

- 同一组回答（10题），使用当前 prompt 各评估 5 次
- 计算 Kappa 系数或标准差
- 对比加入 CoT 后的一致性提升

**实验 B：LLM vs 人类评分相关性**

- 收集 20-30 条候选人真实回答
- LLM 打分 + 3名人类评估者打分
- 计算 Pearson r（预期目标：r > 0.7）

**相关文献**：

- Zheng et al. (2023) "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"
- Panickssery et al. (2024) "LLM Evaluators Recognize and Favor Their Own Generations"
- AlpacaEval, OpenAssistant

---

### 第八章：实验与综合评估

#### 8.1 评估维度


| 维度     | 指标                        | 方法             |
| ------ | ------------------------- | -------------- |
| 面试质量   | 题目专业性、话题多样性、人设一致性         | 人工评估 + 自动检测重复率 |
| 评分可靠性  | Kappa 系数、与人类评分的 Pearson r | LLM vs 人类实验    |
| 用户体验   | 面试真实感、反馈有用性（5分制）          | 用户问卷           |
| RAG 效果 | 技术题幻觉率（有无 RAG 对比）         | 人工标注           |


#### 8.2 消融实验设计

逐一关闭某个模块，测量关键指标下降：

- 关闭 RAG → 技术题准确率
- 关闭 Memory（candidate_profile）→ 问题重复率
- 关闭 CoT → 评分一致性
- 关闭 Few-shot → persona 风格漂移率

---

### 第九章：总结与展望

#### 贡献总结

1. 设计并实现了三层 agent 流水线，解决单一 LLM 角色冲突问题
2. 提出适用于面试场景的 prompt engineering 技法组合
3. 构建四层记忆架构，实现简历和 JD 驱动的个性化面试
4. 通过 RAG 消除技术专项面试的幻觉问题
5. 设计 LLM-as-Judge 评估体系，并验证其可靠性

#### 局限性

- 依赖单一商业 LLM（DeepSeek），稳定性受 API 限制
- 题库初始覆盖有限，依赖人工维护
- 语音模式 STT 精度影响评估准确性

#### 未来方向

- 多模态分析（语音语调、停顿分析）
- 跨 session 学习（记住上一次面试的薄弱点）
- 多语言支持（英文面试场景）

---

## 二、16个改进项 → 5大方向归类

### 方向一：Prompt Engineering


| #   | 改进内容                                                               | 优先级 | 实现位置                                             |
| --- | ------------------------------------------------------------------ | --- | ------------------------------------------------ |
| 1   | 自由面试围绕同一话题不放（strategy prompt 加已覆盖话题禁区规则）                           | P0  | `strategy_prompts.py`                            |
| 3   | 参考答案死板（改写 `_model_answer` prompt，去除显式 STAR 标题，temperature 0.5→0.7） | P0  | `feedback.py`                                    |
| 9   | 参考答案两轮生成 + 维度焦点（self-critique 两轮 LLM call）                         | P2  | `feedback.py`                                    |
| 13  | 自适应难度（strategy prompt 加历史得分参数，动态调整难度指令）                            | P3  | `strategy_prompts.py`                            |
| 14  | 问题类型多样化（strategy 决定题型，interviewer 按类型出题）                           | P3  | `strategy_prompts.py` + `interviewer_prompts.py` |
| 16  | 开场白个性化（根据简历摘要生成第一个具体问题）                                            | P3  | `interviewer_prompts.py`                         |


### 方向二：Multi-Agent Orchestration


| #   | 改进内容                                               | 优先级 | 实现位置                              |
| --- | -------------------------------------------------- | --- | --------------------------------- |
| 11  | 用户纠正面试官 mid-interview（HITL：用户输入作为 SYSTEM 消息注入对话历史） | P2  | 新增 `/correction` endpoint + 前端 UI |


### 方向三：Memory Systems


| #   | 改进内容                                                                | 优先级 | 实现位置                                                |
| --- | ------------------------------------------------------------------- | --- | --------------------------------------------------- |
| 4   | 公司 + JD 全链路（加 `job_description` 字段，setup 页面加输入，注入三个 agent 的 prompt） | P1  | `models.py` + `sessions.py` + 三个 prompts + 前端 setup |
| 5   | 简历驱动个性化（session 创建时 LLM 解析简历，结构化摘要注入 interviewer prompt）            | P1  | `sessions.py` + `interviewer_prompts.py`            |
| 12  | candidate_profile_json 注入面试官（working memory 跨 agent 共享）             | P2  | `interviewer_prompts.py`                            |


### 方向四：RAG


| #   | 改进内容                                     | 优先级 | 实现位置                   |
| --- | ---------------------------------------- | --- | ---------------------- |
| 6   | 技术专项题库 + 检索增强出题（建题库 + 关键词/向量检索 + LLM 改写） | P1  | 新增 `question_bank/` 模块 |


### 方向五：LLM-as-Judge


| #   | 改进内容                                | 优先级 | 实现位置                          |
| --- | ----------------------------------- | --- | ----------------------------- |
| 8   | 面试复盘逐句标注（LLM 逐句评判，前端高亮渲染）           | P2  | `feedback.py` + 前端 feedback 页 |
| 10  | 参考答案 vs 用户答案差异分析（比较式 LLM 评估，输出具体差距） | P2  | `feedback.py`                 |
| 15  | 实时评分显示（文字模式每题回答后即时展示维度得分）           | P3  | 前端 interview 页（API 已支持）       |


---

## 三、立即推进项（不属于五大方向的纯工程改动）

这两项是 bug 级别的体验问题，与论文方向无关，应立即修复：

### #2 Feedback 页 Markdown 不渲染

**问题**：`model_answer` 是 LLM 生成的 markdown 格式文本（含 `**粗体`**、`- 列表`），但 feedback 页面当作纯文本展示，显示原始 markdown 符号。

**解法**：安装 `react-markdown`，替换 feedback 页中 `model_answer` 的渲染方式。

```bash
cd frontend && npm install react-markdown
```

```tsx
import ReactMarkdown from 'react-markdown'
// 替换：<p>{evaluation.model_answer}</p>
// 为：<ReactMarkdown>{evaluation.model_answer}</ReactMarkdown>
```

**实现位置**：`frontend/app/feedback/[sessionId]/page.tsx`

---

### #7 流式输出（Streaming）

**问题**：LLM 生成完整响应（2-4 秒）后一次性返回，文字模式下等待感强，体验像在"等一个慢 AI"。

**解法**：后端改为 Server-Sent Events（SSE）streaming 输出，前端逐 token 接收展示。

后端改动（`interview.py`）：

```python
from fastapi.responses import StreamingResponse

async def stream_response():
    async for chunk in llm_client.stream(messages):
        yield f"data: {chunk}\n\n"

return StreamingResponse(stream_response(), media_type="text/event-stream")
```

前端改动（`interview/[sessionId]/page.tsx`）：

```typescript
const response = await fetch(url, { method: 'POST', body: ... })
const reader = response.body.getReader()
// 逐 chunk 读取并 setState 追加到显示文本
```

**注意**：流式输出仅适用于文字模式，语音模式需要等完整文本才能 TTS。

---

## 四、推进优先级总览

```
立即推进（本次）
  ├── #2  Markdown 渲染修复
  └── #7  流式输出

第一阶段（P0，1-2天）
  ├── #1  自由面试话题重复修复
  └── #3  参考答案 prompt 改写

第二阶段（P1，1周，定位B核心基础）
  ├── #4  公司 + JD 全链路
  ├── #5  简历驱动个性化
  └── #6  技术专项题库 + RAG

第三阶段（P2，大幅提升学习价值）
  ├── #8  逐句标注复盘
  ├── #9  参考答案两轮生成
  ├── #10 差异分析
  ├── #11 用户纠正面试官
  └── #12 candidate_profile 注入面试官

第四阶段（P3，体验打磨）
  ├── #13 自适应难度
  ├── #14 问题类型多样化
  ├── #15 实时评分显示
  └── #16 开场白个性化
```

---

*文档生成时间：2026-06-02*
*基于两轮对话讨论整理，供后续 agent 接力推进*