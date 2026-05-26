# MockMate 科研创新机制交接文档
> 供后续 Agent 或团队成员直接参考，无需任何前置对话记忆。
> 本文档描述所有已讨论的科研导向创新机制，分为「MVP已实现」「后续规划」两类。

---

## 一、研究定位

**论文题目方向：** 基于多 Agent 协作与动态上下文感知的智能模拟面试系统

**核心研究问题：**
> 现有模拟面试工具存在两个根本缺陷：
> 1. 上下文截断——面试官"忘记"候选人早期信息，无法基于完整画像追问
> 2. 问题无差异——不管回答质量好坏，按固定题库念题，无真实面试的动态决策

**本系统的研究贡献：**
1. 三 Agent 角色分离架构（解决单 Agent 角色污染问题）
2. 基于对话历史的动态问题生成（替代静态题库）
3. 固定维度池中的动态维度激活（评估维度随候选人表现自适应）
4. 预设模式 vs 动态模式对比（消融实验基础）

**论文格式要求：**
中英文摘要、文章综述、文献综述、方法、实验与分析、结论、参考文献
单倍行距，至少18页，毕业设计论文格式（不需要首页）

---

## 二、已在 MVP 中实现的创新机制

### 机制1：三 Agent 角色分离架构

**问题：** 单 Agent 合并 Prompt 时产生角色污染（Role Contamination）
- 同时扮演"友好面试官" + "严格评委" + "策略决策者"，三种角色互相软化
- LLM sycophancy 导致评分偏高、追问不够犀利
- Prompt 越来越长，接近上下文限制

**解决方案：**
```
Interviewer Agent → 只管生成自然对话，受 Persona 约束
Strategy Agent   → 冷静决策（追问/继续/切换），不受对话情绪影响
Evaluator Agent  → 独立评分，无"维持对话流畅"的顾虑
```

**文献支撑：**
- Zheng et al. (2023) "Judging LLM-as-a-Judge" — 生成与评估分离提升质量
- Shinn et al. (2023) "Reflexion" — 独立反思 Agent 显著提升任务完成质量
- Park et al. (2023) "Generative Agents" — 多 Agent 角色分工有效性

**实验设计（后续可做）：**
```
消融实验 A：单 Agent（合并） vs 三 Agent（分离）
指标：人类专家对追问针对性的打分（1-5分李克特量表）
假设：三 Agent 追问针对性显著高于单 Agent（p < 0.05）
```

---

### 机制2：基于对话历史的动态问题生成（Level 2）

**问题：** 静态题库出题与候选人实际回答内容脱节，面试官"不听你说的"

**解决方案：**
每道主问题由 Strategy Agent 基于以下上下文动态生成：
```python
context = {
    "job_role": session.profile.target_role,
    "resume": session.profile.resume_text,
    "conversation_history": [最近5轮对话],
    "candidate_profile": session.candidate_profile_json,  # 动态更新的画像
    "covered_topics": [...],     # 已问过的话题，避免重复
    "current_stage": session.state,
    "questions_remaining": session.max_questions - session.question_count,
    "active_dimensions": session.active_dimensions,
}
```

**候选人画像（candidate_profile_json）动态更新：**
```json
{
  "background": {
    "school": "XX大学", "major": "计算机", "internships": ["字节·数据"]
  },
  "strengths_confirmed": ["跨部门协作", "用户调研"],
  "weaknesses_exposed": ["数据量化能力弱", "领导力案例不具体"],
  "key_statements": ["在字节做了一年数据分析", "负责过3人小组"],
  "pending_topics": ["第二段实习的具体产出还没追问"]
}
```

**与静态题库的对比（论文实验）：**
```
指标1：问题与候选人回答内容的语义相关度（BERTScore）
指标2：候选人主观评分（问题是否针对我说的内容）
假设：动态生成 > 静态题库（两项指标均显著）
```

---

### 机制3：固定维度池动态激活

**问题：** 固定5维度无法适配不同岗位、不同候选人表现的评估需求

**15维度池：**
```
通用：相关性、结构性、具体性、影响力、表达清晰度
行为：领导力、协作能力、执行力、抗压能力
技术：数据思维、技术深度、逻辑严密性
潜力：学习能力、创新性、学术潜力（研究生专用）
```

**激活机制：**
- 每场面试开始时，Strategy Agent 根据面试类型+职位选择5个默认维度
- 每轮评估后，Evaluator Agent 检测是否需要激活新维度
  - 候选人提到"我带领了团队" → 激活"领导力"
  - 候选人被追问后仍然模糊 → 激活"具体性"权重加倍
- 雷达图维度随面试进展动态更新（视觉上非常直观）

**论文实验：**
```
固定维度 vs 动态维度激活
指标：与人类专家评估的相关系数（Spearman's ρ）
假设：动态激活与专家判断相关性更高
```

---

### 机制4：预设模式 vs 动态模式

**设计意图：** 为论文消融实验提供明确的对照组

| 维度 | 预设模式（Baseline） | 动态模式（Contribution） |
|---|---|---|
| 问题来源 | 基于阶段+职位的标准提示 | 对话历史驱动生成 |
| 题目数量 | 固定8题 | 6-12题（Agent决定） |
| 维度 | 固定5个 | 动态激活（最多7个） |
| 追问触发 | 规则触发（回答<50词等） | Evaluator Agent评分驱动 |
| 可重现性 | 高（适合实验） | 低（每场独特） |

**消融实验设计：**
```
组1：预设模式（无动态）
组2：动态问题 + 固定维度（部分动态）
组3：完整动态模式（全动态）
指标：候选人满意度 / 问题针对性评分 / 面试完成率
```

---

## 三、后续规划的科研创新机制（MVP未实现，但已设计）

### 后续机制1：面试专用三层记忆系统

**来源：** 项目提案中的核心创新点1

**问题：** 长面试（50轮+）中早期信息被上下文截断遗忘

**三层结构设计：**

```
Layer 1｜核心事实层（永不压缩，整场持久）
候选人画像 JSON，每轮更新：
{
  "background": {...},
  "strengths_confirmed": [...],
  "weaknesses_exposed": [...],
  "key_statements": [...],
  "pending_followup": [...]
}

Layer 2｜摘要压缩层（已完成问题的压缩记录）
每题结束后压缩为1-2句摘要：
"行为题①-领导力：候选人描述带3人完成策划，未量化结果，评分3.2/5，pending追问"

Layer 3｜近期原文层（最近5轮完整对话）
保证追问的语言自然连贯
```

**重要性打分规则（规则触发，不调LLM，执行快）：**
| 维度 | 判断逻辑 |
|---|---|
| 信息新鲜度 | 是否包含之前未提过的事实 |
| 评估影响力 | 是否改变了对候选人某维度的判断 |
| 引用频率 | 是否被后续轮次连续追问 |

**实验设计：**
```
无记忆（baseline） vs 仅Layer3 vs Layer2+3 vs 完整三层
指标：多跳追问准确率（能否追问5轮前的内容）
预期结果：
  无记忆         → 追问准确率 ~35%
  仅Layer3       → ~52%
  Layer2+3       → ~65%
  完整三层        → ~78%
```

**实现要点：**
- Token 消耗折线图（三层记忆 vs 原始全量）：证明"次线性增长"
- 可视化：面试界面侧边栏实时展示三层记忆状态（演示效果极强）

**需要阅读的文献：**
- MemGPT (Packer et al., 2023) — 分层记忆管理
- MapReduce for Long-context (Wu et al., 2021)
- Cognitive Architectures for LLM Agents (Sumers et al., 2023)

---

### 后续机制2：跨轮一致性检测

**来源：** 项目提案中的核心创新点4

**问题：** 候选人可能在不同轮次说出矛盾信息，真实面试官会追问

**实现逻辑：**
```python
def check_consistency(current_statement, key_statements_history):
    # 检测数字矛盾（正则提取时间/数量/比例等）
    # 例：第5轮"做了一年" vs 第28轮"那半年的实习"
    # 检测到矛盾 → Strategy Agent 标记 → 下一轮追问
    pass
```

**触发追问示例：**
> "你之前提到这段实习做了一年，但刚才你说是半年，能帮我确认一下吗？"

**实验设计：**
- 在候选人回答中植入已知矛盾，测试系统检测率
- 与人类面试官的矛盾检测率对比

---

### 后续机制3：多 Agent 消融实验

**研究问题：** 三 Agent 分离是否真的优于单 Agent？增加的开销是否值得？

**实验设计：**
```
组A：单 Agent（合并 Prompt）
     - 一个 Prompt 同时处理对话生成、评分、策略决策
     
组B：双 Agent（Interviewer + Evaluator合并Strategy）
     
组C：三 Agent（完整分离）

评估指标：
1. 追问触发准确率（人类专家判断：是否应该在这里追问）
2. 评分与人类专家的一致性（Cohen's Kappa）
3. 候选人满意度（主观问卷，1-5分）
4. 延迟 vs 质量权衡曲线

预期：三Agent在质量指标上显著优于单Agent，延迟增加在可接受范围
```

---

### 后续机制4：真实 RAG 接入（JD 知识库）

**来源：** 当前 MVP 用 LLM 参数记忆，后续升级为真实 RAG

**实现方案：**
```
数据收集：
  - 爬取各大招聘平台 JD（200-500条/岗位类型）
  - 结构化存储：{job_title, company_type, requirements, responsibilities}

向量数据库：
  - ChromaDB 或 FAISS
  - Embedding 模型：text-embedding-3-small 或 BGE-M3

检索-增强流程：
  候选人输入目标职位 → 检索相关 JD → 注入 Strategy Agent 上下文
  → 生成针对该职位真实要求的问题

论文贡献：
  参数记忆 vs RAG增强：问题与真实JD要求的对齐度对比（BERTScore）
```

**需要阅读的文献：**
- Lewis et al. (2020) "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
- Self-RAG (Asai et al., 2023)
- HyDE (Gao et al., 2022)

---

### 后续机制5：话语质量分析（Discourse Analysis）

**来源：** 痛点6，P4负责

**检测指标：**
```python
discourse_metrics = {
    "filler_word_count": ...,     # 填充词："那个"、"就是说"、"um"
    "avg_sentence_length": ...,
    "passive_voice_ratio": ...,
    "word_count": ...,
    "star_completeness": {
        "situation": bool,
        "task": bool,
        "action": bool,
        "result": bool,
    }
}
```

**反馈展示：** 在 Feedback 页增加"表达质量"专项分析模块

**论文贡献：** 语言学特征与面试评分相关性研究（回归分析）

---

### 后续机制6：自我评估校准（Meta-cognition）

**来源：** 痛点8，已从MVP移除，但有论文价值

**机制：**
- 每道题回答后，先让候选人为自己打分
- 展示 AI 评分
- 追踪"自我认知偏差"随时间变化（Dunning-Kruger 效应研究）
- 苏格拉底式反思提示：不给答案，引导自我审视

**实验设计：**
- 对照组：只看AI评分
- 实验组：先自评再看AI评分
- 指标：多场练习后自我评估准确度提升幅度

---

### 后续机制7：IRT 自适应题目难度（Item Response Theory）

**来源：** 痛点2延伸，未纳入MVP

**机制：**
- 为每道题估计难度参数 θ（0-1）
- 根据候选人历史得分动态选择下一题难度
- 类比计算机自适应测试（CAT）

**论文贡献：** IRT 是教育测量学成熟理论，移植到面试训练是跨领域创新

**需要阅读的文献：**
- van der Linden & Hambleton (1997) "Handbook of Modern Item Response Theory"
- Computerized Adaptive Testing 相关综述

---

### 后续机制8：幻觉检测与RAG接地

**来源：** 痛点7

**问题：** AI 面试官可能编造公司文化、岗位要求等信息，破坏可信度

**实现方案：**
```
NLI验证层：
  - 检索公司/岗位信息（RAG）
  - 生成内容通过 NLI 模型验证是否有文档依据
  - 无依据的陈述自动替换为通用表述

实验设计：
  - 构造幻觉测试集（100条已知事实的面试官发言）
  - 测量幻觉率（无RAG vs 有RAG vs 有RAG+NLI验证）
```

---

## 四、论文实验规划总览

### 实验一：动态问题生成 vs 静态题库（核心实验）
```
实验组：动态生成（基于对话历史）
对照组：静态题库随机选题

指标A：问题与候选人前序回答的BERTScore相关度
指标B：候选人主观评分（这道题针对我说的内容吗？1-5分）
指标C：追问准确率（该追问时追问了吗？人类专家标注）

招募：5-10名同学作为候选人，每人分别体验两种模式
分析：配对t检验
```

### 实验二：三Agent消融实验
```
配置A：单Agent（baseline）
配置B：双Agent
配置C：三Agent（完整）

指标：追问针对性评分（人类专家盲评）、评分一致性（Cohen's Kappa）
```

### 实验三：动态维度激活效果
```
固定维度 vs 动态激活
指标：与人类专家评估的Spearman相关系数
```

### 实验四（若时间允许）：三层记忆消融
```
无记忆 → 仅近期层 → 近期+压缩层 → 完整三层
指标：长面试（50轮）中的跨轮追问准确率
```

---

## 五、文献综述方向

以下为需要精读并引用的论文方向（P3负责查找文献）：

**LLM Agent 架构：**
- ReAct (Yao et al., 2022)
- Generative Agents (Park et al., 2023)
- AgentBench (Liu et al., 2023)
- LLM-as-Judge (Zheng et al., 2023)

**记忆与长上下文：**
- MemGPT (Packer et al., 2023)
- Cognitive Architectures for LLM Agents (Sumers et al., 2023)
- Lost in the Middle (Liu et al., 2023) — 长上下文中间信息遗忘问题

**RAG 与检索增强：**
- RAG (Lewis et al., 2020)
- Self-RAG (Asai et al., 2023)
- Survey on RAG (Gao et al., 2023)

**对话系统与面试相关：**
- 自动面试评估相关论文
- 教育对话系统综述
- Conversational AI Evaluation

**教育测量与自适应学习：**
- IRT 相关综述
- Knowledge Tracing (BKT) 相关论文

---

## 六、分工建议

| 团队成员 | 负责研究方向 | 产出 |
|---|---|---|
| P1（组长） | 系统架构+三Agent+动态问题生成 | MVP实现+方法章节 |
| P2 | 评估维度设计+LLM-as-Judge | 实验设计+评分章节 |
| P3 | 文献综述+RAG规划 | 文献综述章节+参考文献 |
| P4 | 话语分析+可视化+实验执行 | 实验结果+图表 |

---

## 七、论文结构建议

```
摘要（中英）
  - 问题：现有工具上下文截断+问题无差异
  - 方法：三Agent架构+动态生成+维度激活
  - 实验：消融实验+用户研究
  - 结论：动态系统显著优于预设系统

1. 引言
  - 模拟面试工具现状与局限
  - 本文贡献（3-4个bullet）

2. 相关工作（文献综述）
  - LLM对话Agent
  - 面试评估系统
  - 自适应学习系统

3. 系统设计（方法）
  3.1 整体架构
  3.2 三Agent协作机制
  3.3 动态问题生成
  3.4 维度动态激活
  3.5 预设 vs 动态模式

4. 实验与分析
  4.1 实验设置
  4.2 动态生成 vs 静态题库
  4.3 三Agent消融实验
  4.4 维度激活效果
  4.5 用户研究

5. 讨论
  5.1 局限性（单一LLM依赖、RAG尚未接入）
  5.2 未来工作（三层记忆、一致性检测、IRT自适应）

6. 结论

7. 参考文献（20+篇）
```

---

*文档版本：Research v1.0 | 最后更新：2025-05-25*
