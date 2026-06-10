# Prompt Change Log

This document records prompt/LLM-behavior changes, the before/after logic, and verification results.

## 2026-06-10

### Two-round self-critique for reference answers

Changed file:
- `backend/app/api/feedback.py`

Problem observed:
- Reference answer generation used only one critique/rewrite pass after the initial draft.
- Some answers could still be too short, leak critique wording, lose self-introduction follow-up hooks, or sound template-like.
- Self-introduction answers are especially sensitive because they need enough substance for later follow-up questions.

Before behavior:
- Reference answer path:
  - draft generation
  - one self-critique rewrite
- No deterministic quality check after the rewrite.
- If the critique output leaked words like "critique" / "批判" or over-compressed a self-introduction, the answer could be saved directly.

After behavior:
- Reference answer path:
  - draft generation
  - self-critique round 1 rewrite
  - self-critique round 2 rewrite
  - deterministic quality check
  - targeted repair only if quality issues are detected
- The second critique round checks:
  - whether the answer directly answers the question
  - whether it preserves the candidate's original story
  - whether personal contribution is clear
  - whether self-introduction keeps enough follow-up hooks
  - whether the answer avoids fabricated firm facts, exaggeration, and template-like phrasing

Optimized prompt excerpt:
```text
请进行第{round_no}轮自我批判并改进它：
1. 是否完整覆盖背景、经历/项目、能力亮点和岗位动机？
2. 是否保留了足够可追问线索，而不是过度压缩？
3. 个人贡献是否清晰？表达是否自然？
4. 是否有编造确定事实、过度夸大或模板化表达？
直接输出改进后的最终版本，不要输出批判分析过程。
```

Quality check logic:
- Detect empty output.
- Detect leaked critique markers:
  - `批判`
  - `问题：`
  - `改进点`
  - `critique`
  - `issues:`
  - `improved version`
  - `final version`
  - `self-critique`
- Detect too-short reference answers:
  - Chinese self-introduction: `<280` Chinese characters
  - English self-introduction: `<180` words
  - Chinese normal answer: `<40` Chinese characters
  - English normal answer: `<45` words
- Detect too-long reference answers:
  - Chinese self-introduction: `>560` Chinese characters
  - English self-introduction: `>360` words
  - Chinese normal answer: `>190` Chinese characters
  - English normal answer: `>180` words

Comparison data:

| Item | Before | After |
|---|---:|---:|
| Draft generation | 1 | 1 |
| Self-critique rewrite rounds | 1 | 2 |
| Deterministic quality check | 0 | 1 |
| Targeted repair on failed quality check | 0 | 1 optional |
| Checks for critique leakage | no | yes |
| Checks for self-intro over-compression | no | yes |

Local quality-check test results:

| Case | Expected | Result |
|---|---|---|
| empty output | `empty` | passed |
| critique text leaked | `critique_leak` | passed |
| short self-introduction | `self_intro_too_short` | passed |
| short normal answer | `answer_too_short` | passed |
| overlong normal answer | `too_long` | passed |
| concrete 53-character Chinese answer | no issue | passed |

Verification:
- `python -m py_compile backend\app\api\feedback.py`
- Deterministic quality-check cases passed with Unicode-safe Chinese test strings.

Residual risks:
- This increases LLM calls for each reference answer from 2 to 3 in the normal path, and to 4 only when quality repair is needed.
- Quality check is deterministic and catches structural issues; semantic quality still depends on the two self-critique rewrites and should be eval-tested on final reports.

### Robust evaluation for hollow, brief, and off-topic answers

Changed files:
- `backend/app/llm/prompts/evaluator_prompts.py`
- `backend/app/agents/evaluator.py`

Problem observed:
- Hollow, overly brief, and off-topic answers were all easy to collapse into a generic "not specific enough" diagnosis.
- This made feedback less actionable and could produce the wrong follow-up behavior:
  - hollow answer -> should ask for project/data/method/owned action
  - brief answer -> should ask for one missing evidence type
  - off-topic answer -> should redirect to the original question
  - refusal/no experience -> should score low and provide a preparation path, not repeatedly probe the same fact

Before prompt/runtime behavior:
- Evaluator prompt mentioned brief and vague answers, but did not require an explicit answer-type classification step.
- Score boundaries existed for weak/invalid answers, but there was no dedicated scoring cap for:
  - short but content-light answers
  - hollow but fluent answers
  - clearly off-topic answers
  - explicit refusal / no relevant experience
- Runtime fallback only forced probes for `<50` answers and buzzword-heavy vague answers.
- Runtime did not distinguish off-topic redirection from evidence-completion probes.

Optimized prompt logic:
- Evaluation now starts with answer-type classification:
  - normal answer
  - very short answer
  - hollow answer
  - off-topic answer
  - refusal/invalid answer
- Added abnormal-answer score boundaries:
  - short but relevant with concrete evidence: can score 4-6
  - short and content-light: usually <= 4
  - hollow but relevant: usually <= 4
  - clearly off-topic: usually <= 2
  - explicit refusal / no experience: usually <= 2
  - almost blank: dimensions near 0
- Added feedback requirements:
  - off-topic feedback must say "return to the core question" and provide a rewrite frame
  - short-answer feedback must name the missing evidence type
  - hollow-answer feedback must ask for a concrete project/experiment/paper/business scenario and at least one field such as metric definition, sample size, method, or owned action
- Added probe rule:
  - off-topic but recoverable answers should trigger a redirecting follow-up
  - explicit refusal/no experience should not repeatedly trigger the same probe

Optimized prompt excerpt:
```text
第一步：先做回答类型判定
- 正常回答
- 过短回答
- 空洞回答
- 离题回答
- 拒答/无效回答

异常回答评分边界：
- 过短但相关：若包含具体技术/方法/数字/个人动作，分数可在4-6；若只有"做过/了解/还行"，分数通常不超过4
- 空洞但相关：若只有抽象词和态度，分数通常不超过4
- 明显离题：通常不超过2；feedback 要先指出未回应问题核心
- 明确拒答/不知道/没经历：通常不超过2；不要编造候选人能力，不要追问同一事实
```

Runtime changes:
- Added deterministic answer issue classifier:
  - `refusal`
  - `off_topic`
  - `vague`
  - `too_short`
- Added score caps:
  - `refusal`: max 2.0
  - `off_topic`: max 2.0
  - `vague`: max 4.0
  - `too_short` without concrete evidence: max 4.0
  - `too_short` with concrete evidence: no hard score cap
- Added issue-specific feedback post-processing.
- Added off-topic redirect probe reason.
- Refusal answers no longer force a follow-up probe.

Comparison data from local deterministic checks:

| Case | Example shape | Detected issue | Score cap | Forced probe |
|---|---|---|---:|---|
| brief | "做过，挺顺利的。" | `too_short` | 4.0 | yes, ask for concrete case/contribution/result |
| vague | "拉齐认知、形成闭环、赋能业务、沉淀体系化方法论" | `vague` | 4.0 | yes, ask for project/data/method/owned action |
| off_topic | "今天天气不错，我最近在看电影。" | `off_topic` | 2.0 | yes, redirect to core question |
| refusal | "我没有相关经验，不太会。" | `refusal` | 2.0 | no repeated probe |

Verification:
- `python -m py_compile backend\app\agents\evaluator.py backend\app\llm\prompts\evaluator_prompts.py`
- Local deterministic classifier checks passed for brief, vague, off-topic, and refusal cases.

Residual risks:
- Off-topic detection is heuristic. It uses explicit unrelated-topic terms plus low-overlap checks, so subtle off-topic answers may still rely on the LLM prompt.
- Chinese shell encoding on Windows can corrupt ad-hoc terminal literals; deterministic checks used Unicode-safe construction where needed.

### Interviewer persona few-shot style separation

Changed file:
- `backend/app/llm/prompts/interviewer_prompts.py`

Problem observed:
- The three interviewer personas had different descriptions, but the few-shot examples were not differentiated enough.
- Sarah, Marcus, and Alex could still converge toward a generic "ask for more detail" style during follow-up turns.

Before prompt behavior:
- Each persona had 3 dialogue examples per language.
- Persona descriptions focused on broad adjectives:
  - Sarah: warm and encouraging
  - Marcus: direct and demanding
  - Alex: fast-paced and hypothetical
- There was no explicit "avoid this other persona's style" boundary.
- There was no explicit probe granularity line defining what kind of missing evidence each persona should prefer.

Optimized prompt logic:
- Sarah now has a supportive HR style:
  - first acknowledge the promising part
  - ask open questions
  - prefer context, motivation, personal role, collaboration, and reflection
  - avoid Marcus/Alex phrases such as "define that", "give me numbers", or compressed deadline hypotheticals
- Marcus now has a technical audit style:
  - no small talk
  - validate technical judgment, personal contribution, metric credibility, root cause, complexity, architecture trade-off, and production validation
  - avoid Sarah-style warm setup and Alex-style rapid product hypotheticals
- Alex now has a product pressure-test style:
  - switch scenarios quickly
  - use constraints, conflict, and resource compression
  - prefer prioritization, trade-off, minimum viable validation, and risk control
  - avoid Sarah-style emotional support and Marcus-style prolonged technical auditing

Optimized prompt excerpt:
```text
Sarah:
追问粒度：优先问经历背景、沟通动机、个人角色、反思成长；不要像技术审查一样连续逼问指标和实现细节。
禁用风格：不要说"定义一下"、"别说团队"、"给我数字"、"3天内怎么做"这类强压话术。

Marcus:
追问粒度：优先问技术方案、根因定位、指标口径、复杂度、架构取舍、上线验证；不要做情绪安抚。
禁用风格：不要用"我很好奇"、"听起来很棒"、"可以带我回到场景吗"这类温柔铺垫；不要像 Alex 一样频繁换假设场景。

Alex:
追问粒度：优先问目标拆解、优先级、取舍、最小验证、风险兜底；不要深挖代码实现，也不要长时间安抚。
禁用风格：不要用 Sarah 的鼓励式铺垫；不要像 Marcus 一样停留在某个技术指标上连续审查。
```

Few-shot changes:
- Sarah added a graduate-interview example that asks about academic motivation through a supportive experience-based question.
- Marcus added a graduate-interview example that asks the candidate to name one paper and state problem definition, method, and dataset.
- Alex added a graduate-interview example that turns research interest into a two-week validation plan with data and continuation criteria.
- Existing examples were rewritten so the same vague inputs produce visibly different persona reactions:
  - Sarah: "你可以带我回到当时的项目里吗？"
  - Marcus: "'我们'太宽了。你个人写了哪些代码、改了哪个模块..."
  - Alex: "如果只给你3天拿到方向性结论，你今天下午先做哪件事？"

Comparison data:

| Prompt block | Before examples | After examples | Before avoid-style rules | After avoid-style rules | Before probe granularity | After probe granularity |
|---|---:|---:|---:|---:|---:|---:|
| zh_sarah | 3 | 4 | 0 | 1 | 0 | 1 |
| zh_marcus | 3 | 4 | 0 | 1 | 0 | 1 |
| zh_alex | 3 | 4 | 0 | 1 | 0 | 1 |
| en_sarah | 3 | 4 | 0 | 1 | 0 | 1 |
| en_marcus | 3 | 4 | 0 | 1 | 0 | 1 |
| en_alex | 3 | 4 | 0 | 1 | 0 | 1 |

Prompt surface size comparison:

| Prompt block | Before chars | After chars |
|---|---:|---:|
| zh_sarah | 484 | 727 |
| zh_marcus | 473 | 647 |
| zh_alex | 402 | 597 |
| en_sarah | 1362 | 1937 |
| en_marcus | 1159 | 1682 |
| en_alex | 992 | 1608 |

Verification:
- `python -m py_compile backend\app\llm\prompts\interviewer_prompts.py`
- Prompt construction smoke test passed for all 6 combinations:
  - `zh/en × sarah/marcus/alex`
  - generated message arrays had valid system and user turns

Residual risks:
- This is prompt-surface and construction verification, not a live LLM style-classification eval.
- A stronger next eval would generate one response per persona for the same scenario and have LLM-as-judge score style distinctiveness.

## 2026-06-07

### Probe and feedback actionability refinement

Changed files:
- `backend/app/llm/prompts/evaluator_prompts.py`
- `backend/app/agents/evaluator.py`

Problem observed:
- `brief_answerer` and `vague_answerer` scenarios had poor feedback actionability, sometimes scoring only 1 in judge evaluation.
- Very short answers and hollow buzzword answers should trigger follow-up probes, but the model sometimes continued to the next main question.

Before prompt/runtime behavior:
- Probe rules mentioned unexplored details and vague answers, but did not make `<50` length an explicit hard trigger.
- Feedback only needed to be "specific", which still allowed generic text like "needs more detail" or "needs improvement".
- Probe triggering depended almost entirely on model output.

After prompt behavior:
- Evaluator prompt now has `Rule 0`: answers under 50 Chinese characters / English words must trigger a probe when probe quota allows.
- Evaluator prompt now has `Rule 5`: buzzword-heavy vague answers without concrete project/data/method/owned action must trigger a probe.
- Feedback must include "evidence judgment from this answer + one actionable fix".
- Feedback must include at least one concrete technical/method term, explicit behavioral suggestion, or measurable target.
- Generic feedback such as "需要加强", "更具体", "needs improvement", or "gain more experience" is explicitly forbidden.

After runtime behavior:
- Evaluator now has deterministic probe fallback:
  - `<50` Chinese characters / English words -> force `is_probe_triggered=true` if probing is allowed.
  - Buzzword-heavy answers with no concrete evidence -> force probe if probing is allowed.
- Evaluator now post-processes hollow feedback:
  - Adds dimension-specific suggestions for `tech_depth`, `data_thinking`, `academic`, `specificity`, `impact`, `structure`, and `expression`.
  - Example: data-thinking feedback receives suggestions like metric definition, sample size, SQL/Python analysis steps, or A/B test result.

Expected comparison:
- Before: brief answers like "接触过，做过类似的事" could receive a generic low score and no follow-up.
- After: brief answers force a probe asking for concrete case/personal contribution/quantified result.
- Before: vague answers using terms like "闭环、赋能、对齐、体系化" could pass as fluent but empty.
- After: such answers trigger a probe unless they include concrete project, metric, method, or owned action.
- Before: feedback could say only "需要加强".
- After: feedback is supplemented with a concrete next step tied to the dimension.

Verification:
- `python -m py_compile backend\app\agents\evaluator.py backend\app\llm\prompts\evaluator_prompts.py`
- Manual local checks passed for short-answer probe forcing, vague-answer probe forcing, and feedback actionability post-processing.
- Canned evaluator+judge run, 2026-06-08:
  - `brief_answerer`: `followup_logic=5`, `feedback_actionability=5`; all 3 canned short answers were marked `is_probe_triggered=true`.
  - `vague_answerer`: `feedback_actionability=5`; all 3 canned vague/short answers were marked `is_probe_triggered=true`.
  - `vague_answerer` still received `followup_logic=1` in the canned run because the harness skipped Strategy/Interviewer question generation to avoid timeout, so Judge saw trigger flags but no actual follow-up question turns.

Residual risks:
- The `<50` hard threshold may probe short but partially specific answers; this is intentional for now because the eval scenarios penalize missing follow-up on short answers.
- Buzzword detection is heuristic and may need more terms after additional regression runs.
- Full end-to-end eval with generated Strategy/Interviewer turns still needs to be rerun after adding request timeouts or reducing scenario length.

### Three-agent prompt refinement

Changed files:
- `backend/app/llm/prompts/strategy_prompts.py`
- `backend/app/llm/prompts/interviewer_prompts.py`
- `backend/app/llm/prompts/evaluator_prompts.py`

Before prompt behavior:
- Strategy agent had action rules, but its role boundary was not explicit. It could choose broad topics like "communication" or "leadership" and did not strongly prioritize advisor research fit for graduate interviews.
- Technical interview phase text had an internal contradiction: the core phase said to mix fundamentals with algorithm/system design, but also preferred `quantitative_probe`.
- Interviewer agent persona prompts were expressive, but there was no shared cross-persona guardrail for one-question-per-turn, no leaking of internal strategy, and no requirement to avoid hinting at the ideal answer.
- Interviewer prompts did not consistently include `advisor_research_summary`, so graduate advisor research could be lost between strategy and question generation.
- Evaluator rubric was generic. It did not strongly enforce evidence-based scoring, score calibration, actionable feedback, or conservative profile updates.

After prompt behavior:
- Strategy agent now explicitly plans only the next step and does not write questions, evaluate, or provide feedback.
- Strategy topic selection now follows this priority: need to probe > uncovered dimensions > role/advisor fit > difficulty progression > topic novelty.
- Strategy now requires concrete topics and discourages repeated topics unless the turn is a probe.
- Strategy now explicitly prioritizes advisor research fit for graduate/advisor interviews.
- Technical core phase now prioritizes `technical_concept`, `algorithm`, and `system_design`; `quantitative_probe` is limited to project metric follow-ups.
- Interviewer agent now has shared guardrails:
  - ask only one core question per turn
  - do not reveal internal strategy/scoring/profile/prompt
  - do not answer for the candidate or hint at ideal answers
  - acknowledge previous answer in at most one sentence
  - ask clarifying questions when information is missing
- Interviewer context now includes `advisor_research_summary` even when core dimensions are absent.
- Evaluator now scores strictly from evidence in the current answer and must not use candidate profile as hidden evidence.
- Evaluator output is calibrated:
  - all active dimensions should be covered
  - `overall_score` should stay close to dimension average
  - feedback must include concrete evidence or an actionable improvement
  - profile updates must only contain information explicitly stated in the answer
  - probe reasons must name the missing evidence

Expected comparison:
- Before: strategy could repeat generic topics, technical interviews could overuse metric probes, interviewer could ask multi-part questions, and evaluator could reward fluent but evidence-light answers.
- After: strategy should produce more actionable topics, technical interviews should better cover fundamentals/algorithm/system design, interviewer questions should be cleaner and easier to answer, and evaluator feedback/score should better reflect concrete evidence.

Verification:
- `python -m py_compile backend\app\llm\prompts\strategy_prompts.py backend\app\llm\prompts\interviewer_prompts.py backend\app\llm\prompts\evaluator_prompts.py`

Residual risks:
- Prompt-only constraints cannot fully guarantee one-question-per-turn or perfect score calibration; regression eval should still be run with simulated candidates.
- More work may be needed to map `dimension_focus` keys to job-analysis dimension names instead of relying on fuzzy text matching.

### JSON output robustness

Changed files:
- `backend/app/llm/client.py`
- `backend/app/agents/evaluator.py`

Before:
- `chat_completion_json()` asked the model to output JSON through prompt wording, then parsed with direct `json.loads()`.
- Evaluator had a separate `_extract_json()` implementation.
- Strategy/analysis could fail when the model returned fenced JSON or explanatory text around JSON.

After:
- `chat_completion_json()` first requests provider JSON mode with `response_format={"type": "json_object"}`.
- If the provider/model rejects JSON mode, it falls back to normal completion.
- All JSON output is parsed by one shared `extract_json_object()` helper.
- The helper supports strict JSON, fenced JSON, surrounding text, and braces inside JSON strings.
- Evaluator now reuses the same parser through `_extract_json = extract_json_object`.

Expected comparison:
- Before: occasional invalid JSON failures from harmless wrappers.
- After: JSON wrappers and mixed text should parse successfully; true malformed JSON still fails loudly.

Verification:
- `python -m py_compile backend\app\llm\client.py backend\app\agents\evaluator.py`
- Manual parser checks passed for strict JSON, fenced JSON, mixed text, and braces inside strings.

### Optimized reference answer for self-introduction

Changed files:
- `backend/app/api/feedback.py`

Before prompt behavior:
- All reference answers used the same short-answer logic.
- Chinese answers were capped at 150 characters.
- English answers were capped at 150 words.
- Self-introduction answers could be over-compressed, losing background, projects, motivation, and follow-up hooks.

After prompt behavior:
- Self-introduction questions are detected separately:
  - Chinese: `自我介绍`, `介绍一下你自己`, `介绍一下自己`, `简单介绍`
  - English: `tell me about yourself`, `introduce yourself`, `brief introduction`, `quick intro`
- Self-introduction reference answer length:
  - Chinese: 350-500 characters
  - English: 220-320 words
- The optimized answer must preserve education/work background, core experience or projects, key strengths, role motivation, technical/business keywords, and follow-up hooks.
- It may remove repetition and filler, but must not collapse the answer into a short summary.
- Missing metrics should use placeholder expressions like `约X%` / `about X%` rather than inventing firm facts.

Expected comparison:
- Before: "self-introduction" could become shorter than the user's original detailed answer.
- After: self-introduction remains rich enough for follow-up questioning while becoming more structured and fluent.

Verification:
- `python -m py_compile backend\app\api\feedback.py`
- Manual self-introduction detector checks passed for Chinese and English examples.

### Graduate advisor search and analysis

Changed files:
- `backend/app/services/web_search.py`
- `backend/app/api/sessions.py`
- `backend/app/api/schemas.py`
- `backend/app/llm/prompts/analysis_prompts.py`
- `frontend/lib/types.ts`
- `frontend/app/setup/page.tsx`

Before prompt/search behavior:
- Graduate search used broad queries such as school + department + interview experiences and advisor + research direction.
- The search query did not strongly prioritize official faculty pages.
- `web-search-analyze` searched with `target_advisor`, but the analysis prompt only received `target_role` and `target_company`; advisor and research direction were not first-class analysis inputs.
- The response schema had no dedicated field for advisor research, so mentor-specific content could disappear into generic `summary`, `key_tips`, or `core_dimensions`.
- Graduate analysis required the user to manually click web search; initial analysis did not search.

After prompt/search behavior:
- Graduate search prioritizes exact advisor-name and official-domain queries, for example:
  - `"王凯" "上海交通大学" "安泰经济与管理学院" "数据挖掘"`
  - `site:acem.sjtu.edu.cn "王凯" "安泰经济与管理学院"`
  - `site:acem.sjtu.edu.cn/faculty "王凯"`
  - `site:scholar.google.com/citations 王凯 上海交通大学`
- Domain hints were added for several Chinese universities, including a department-specific hint:
  - `上海交通大学 + 安泰经济与管理学院 -> acem.sjtu.edu.cn`
- Tavily search uses advanced mode with raw content when available.
- Search output includes query and URL to help the analysis model judge source reliability.
- Graduate analysis receives structured metadata:
  - target school
  - target department/major
  - target advisor
  - research direction
- The prompt requires official school/faculty/lab/publication sources to outrank interview-experience snippets.
- The output schema now includes `advisor_research_summary`.
- If a target advisor is provided, the model must name the advisor and summarize research areas/methods/topics; if not found, it must explicitly say reliable public information was not found instead of substituting generic department information.
- The setup page displays `advisor_research_summary` in a dedicated "导师研究方向" card.
- Graduate setup now first displays basic analysis, then automatically starts web-search enhancement in the background.

Expected comparison:
- Before: a case like `上海交通大学 / 安泰经济与管理学院 / 王凯 / 数据挖掘` could return generic school/department analysis without mentioning 王凯.
- After: advisor-specific official queries should be attempted first, and the UI has a dedicated place for the advisor research summary.

Known reference for manual comparison:
- Wang Kai faculty page: `https://www.acem.sjtu.edu.cn/faculty/wangkai.html`
- Public page indicates research around big data management and analytics, complex graph/social network/financial/e-commerce/spatio-temporal data analysis, AI4Society, AI4Business, LLM, GNN, and efficient graph algorithms.

Verification:
- `python -m py_compile backend\app\api\schemas.py backend\app\api\sessions.py backend\app\llm\prompts\analysis_prompts.py backend\app\services\web_search.py`
- `npm run build`
- Query construction manually checked for the Wang Kai / SJTU Antai case.
- Full live search was not completed locally because a command timed out; the generated high-priority query set was verified.

Residual risks:
- Search providers may still rate-limit, timeout, or return sparse snippets.
- Common Chinese names remain ambiguous if the official page is not indexed or if the school uses unusual URL patterns.
- More department-domain hints may be needed as users test additional schools.
