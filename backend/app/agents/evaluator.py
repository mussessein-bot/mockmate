import re

from app.agents.base import BaseAgent
from app.core.models import InterviewSession, DimensionScore, EvaluationResult
from app.core.memory import merge_profile_update, profile_to_text
from app.core.state_machine import can_probe
from app.core.dimensions import DIMENSION_POOL
from app.llm.client import chat_completion, extract_json_object
from app.llm.prompts.evaluator_prompts import build_evaluator_prompt


_extract_json = extract_json_object


_VAGUE_TERMS_ZH = {
    "闭环", "赋能", "对齐", "抓手", "颗粒度", "拉齐", "沉淀", "体系化",
    "优化", "提升", "协同", "方法论", "心智", "复盘", "推进", "落地",
}
_VAGUE_TERMS_EN = {
    "alignment", "optimize", "optimization", "empower", "framework", "leverage",
    "synergy", "impactful", "strategic", "streamline", "improve", "improvement",
}
_REFUSAL_TERMS_ZH = (
    "不知道", "不清楚", "不会", "不太会", "没做过", "没有经验", "没有相关经验",
    "不了解", "无法回答", "不想回答",
)
_REFUSAL_TERMS_EN = (
    "i don't know", "i do not know", "not sure", "no experience", "never done",
    "can't answer", "cannot answer", "i don't want to answer",
)
_OFF_TOPIC_TERMS_ZH = ("天气", "吃饭", "游戏", "电影", "旅游", "这个问题不重要", "换个话题", "随便聊")
_OFF_TOPIC_TERMS_EN = ("weather", "lunch", "movie", "game", "travel", "change the topic", "not important")
_ZH_STOP_CHARS = set("的是了和在也就都而及与或一个我们你们他们这个那个什么怎么为什么请能可以")
_EN_STOP_WORDS = {
    "the", "and", "for", "you", "your", "that", "this", "with", "about", "what",
    "when", "where", "why", "how", "tell", "describe", "could", "would", "please",
}


def _answer_units(answer: str) -> int:
    if re.search(r"[\u4e00-\u9fff]", answer):
        return len(re.findall(r"[\u4e00-\u9fff]", answer))
    return len(re.findall(r"\b[\w'-]+\b", answer))


def _lacks_specific_evidence(answer: str) -> bool:
    has_number = bool(re.search(r"\d", answer))
    has_named_detail = bool(re.search(r"[A-Za-z][A-Za-z0-9_+#.-]{1,}", answer))
    has_chinese_project_marker = any(token in answer for token in ("项目", "实验", "论文", "模型", "系统", "指标", "样本", "用户", "代码"))
    return not (has_number or has_named_detail or has_chinese_project_marker)


def _has_specific_evidence(answer: str) -> bool:
    return not _lacks_specific_evidence(answer)


def _is_vague_answer(answer: str) -> bool:
    lower = answer.lower()
    zh_hits = sum(1 for term in _VAGUE_TERMS_ZH if term in answer)
    en_hits = sum(1 for term in _VAGUE_TERMS_EN if term in lower)
    return (zh_hits + en_hits) >= 3 and _lacks_specific_evidence(answer)


def _is_refusal_answer(answer: str) -> bool:
    stripped = answer.strip().lower()
    if not stripped:
        return True
    return any(term in answer for term in _REFUSAL_TERMS_ZH) or any(term in stripped for term in _REFUSAL_TERMS_EN)


def _keywords(text: str) -> set[str]:
    lower = text.lower()
    en_words = {w for w in re.findall(r"\b[a-z][a-z0-9_+#.-]{3,}\b", lower) if w not in _EN_STOP_WORDS}
    zh_chars = {c for c in re.findall(r"[\u4e00-\u9fff]", text) if c not in _ZH_STOP_CHARS}
    return en_words | zh_chars


def _is_likely_off_topic(question: str, answer: str) -> bool:
    if not answer.strip() or _is_refusal_answer(answer):
        return False
    lower = answer.lower()
    if any(term in answer for term in _OFF_TOPIC_TERMS_ZH) or any(term in lower for term in _OFF_TOPIC_TERMS_EN):
        return True
    if _answer_units(answer) < 12:
        return False
    question_keywords = _keywords(question)
    answer_keywords = _keywords(answer)
    if len(question_keywords) < 4 or len(answer_keywords) < 4:
        return False
    overlap = question_keywords & answer_keywords
    return len(overlap) == 0 and _lacks_specific_evidence(answer)


def _answer_issue(question: str, answer: str) -> str | None:
    if _is_refusal_answer(answer):
        return "refusal"
    lower = answer.lower()
    if any(term in answer for term in _OFF_TOPIC_TERMS_ZH) or any(term in lower for term in _OFF_TOPIC_TERMS_EN):
        return "off_topic"
    if _is_vague_answer(answer):
        return "vague"
    if _is_likely_off_topic(question, answer):
        return "off_topic"
    if _answer_units(answer) < 50:
        return "too_short"
    return None


def _forced_probe_reason(question: str, answer: str, language: str) -> str | None:
    issue = _answer_issue(question, answer)
    if issue == "refusal":
        return None
    if issue == "off_topic":
        return (
            "回答没有回应当前问题核心，需要追问把候选人拉回到一个具体项目、方法或个人动作。"
            if language == "zh"
            else "Answer did not address the core question; redirect to one concrete project, method, or owned action."
        )
    if issue == "vague":
        return (
            "回答存在较多抽象术语但缺少具体项目、数据、方法或个人动作。"
            if language == "zh"
            else "Answer is buzzword-heavy but lacks a concrete project, data, method, or owned action."
        )
    if _answer_units(answer) < 50:
        return (
            "回答少于50字/词，需要追问一个具体案例、个人贡献或量化结果。"
            if language == "zh"
            else "Answer is under 50 words; probe for a concrete example, personal contribution, or quantified result."
        )
    return None


def _dimension_suggestion(dimension: str, language: str) -> str:
    suggestions_zh = {
        "tech_depth": "补充具体算法/框架/数据库选择，并说明复杂度、瓶颈和取舍。",
        "data_thinking": "补充指标口径、样本规模、SQL/Python分析过程或A/B实验结果。",
        "academic": "补充读过的论文、研究方法、数据集/实验设计及与你方向的匹配点。",
        "specificity": "用一个具体项目说明时间、规模、个人动作和量化结果。",
        "impact": "补充可验证结果，如提升比例、成本下降、延迟变化或用户规模。",
        "structure": "按背景-任务-行动-结果组织，并突出最关键的一步行动。",
        "expression": "先给结论，再用一个具体例子支撑，减少抽象判断。",
        "relevance": "围绕题目补充一个与目标岗位直接相关的项目或研究经历。",
    }
    suggestions_en = {
        "tech_depth": "Add the specific algorithm/framework/database choice plus complexity, bottleneck, and trade-off.",
        "data_thinking": "Add metric definition, sample size, SQL/Python analysis steps, or A/B test result.",
        "academic": "Add papers read, research method, dataset/experiment design, and fit with the target direction.",
        "specificity": "Use one concrete project with timeline, scale, owned action, and quantified result.",
        "impact": "Add verifiable outcome such as lift rate, cost reduction, latency change, or user scale.",
        "structure": "Use context-task-action-result and emphasize the most important action.",
        "expression": "Lead with the conclusion, then support it with one concrete example.",
        "relevance": "Add one role-relevant project or research experience that directly answers the question.",
    }
    return (suggestions_zh if language == "zh" else suggestions_en).get(
        dimension,
        "补充一个具体案例、个人贡献、关键数据和复盘结论。" if language == "zh"
        else "Add one concrete example, personal contribution, key metric, and reflection.",
    )


def _issue_suggestion(issue: str | None, dimension: str, language: str) -> str:
    if language == "zh":
        if issue == "off_topic":
            return "先回到问题核心给出结论，再补一个相关项目、个人动作和指标/方法。"
        if issue == "refusal":
            return "若没有经历，说明准备路径：补一个课程/项目/论文例子，并写清方法、数据和复盘。"
        if issue == "vague":
            return "把抽象表述落到一个具体项目/实验/论文，补充指标口径、样本规模、方法和个人动作。"
        if issue == "too_short":
            return "扩展为STAR结构，至少补充具体案例、个人贡献、量化结果或技术/研究方法。"
    else:
        if issue == "off_topic":
            return "Return to the core question first, then add one relevant project, owned action, and metric/method."
        if issue == "refusal":
            return "If you lack experience, give a preparation path: one course/project/paper example with method, data, and reflection."
        if issue == "vague":
            return "Ground the abstract claim in one project/experiment/paper with metric definition, sample size, method, and owned action."
        if issue == "too_short":
            return "Expand with STAR: add a concrete example, personal contribution, quantified result, or technical/research method."
    return _dimension_suggestion(dimension, language)


def _actionable_feedback(
    feedback: str,
    dimension: str,
    language: str,
    answer: str = "",
    issue: str | None = None,
) -> str:
    stripped = (feedback or "").strip()
    generic_patterns = (
        "需要加强", "有待提高", "继续努力", "积累经验", "更加具体", "不够具体",
        "needs improvement", "be more specific", "gain more experience", "average",
    )
    no_answer_patterns = ("未提供回答", "回答为空", "无回答内容", "未提供任何回答", "no answer", "empty answer")
    has_generic = any(p.lower() in stripped.lower() for p in generic_patterns)
    says_no_answer = any(p.lower() in stripped.lower() for p in no_answer_patterns)
    has_action_signal = bool(re.search(r"\d|SQL|A/B|GNN|LLM|STAR|复杂度|指标|样本|数据集|论文|模型|算法|实验|模块|口径|复盘", stripped, re.IGNORECASE))
    if issue in {"off_topic", "refusal", "vague", "too_short"}:
        suggestion = _issue_suggestion(issue, dimension, language)
        if issue == "off_topic":
            prefix = "本轮未回应问题核心；" if language == "zh" else "This answer did not address the core question; "
            return prefix + suggestion
        if issue == "refusal":
            prefix = "本轮缺少可评分内容；" if language == "zh" else "This answer lacks scorable content; "
            return prefix + suggestion
        if not stripped or has_generic or not has_action_signal:
            prefix = ""
            if issue == "vague":
                prefix = "本轮多为空洞概念；" if language == "zh" else "This answer is mostly abstract; "
            elif issue == "too_short":
                prefix = "本轮回答过短；" if language == "zh" else "This answer is too brief; "
            return prefix + suggestion
    if says_no_answer and answer.strip():
        prefix = "回答过短但并非空白；" if language == "zh" else "The answer is brief but not empty; "
        return prefix + _dimension_suggestion(dimension, language)
    if stripped and not has_generic and has_action_signal:
        return stripped

    suggestion = _dimension_suggestion(dimension, language)
    if not stripped:
        return suggestion
    separator = " 建议：" if language == "zh" else " Suggestion: "
    return f"{stripped}{separator}{suggestion}"


def _score_cap(issue: str | None, answer: str) -> float | None:
    if issue in {"refusal", "off_topic"}:
        return 2.0
    if issue == "vague":
        return 4.0
    if issue == "too_short" and not _has_specific_evidence(answer):
        return 4.0
    return None


class EvaluatorAgent(BaseAgent):
    async def evaluate(
        self,
        question: str,
        answer: str,
        question_index: int,
        is_probe_question: bool,
    ) -> tuple[EvaluationResult, dict]:
        """
        Evaluate a candidate answer.
        Returns (EvaluationResult, profile_update_dict).
        """
        profile_text = profile_to_text(self.session.candidate_profile_json, self.language)
        probe_allowed = can_probe(self.session) and not is_probe_question

        messages = build_evaluator_prompt(
            question=question,
            answer=answer,
            active_dimensions=self.session.active_dimensions,
            dimension_pool=DIMENSION_POOL,
            profile_text=profile_text,
            language=self.language,
            can_probe=probe_allowed,
            job_analysis=self.session.job_analysis or None,
        )

        raw = await chat_completion(messages, temperature=0.1)
        data = _extract_json(raw)
        answer_issue = _answer_issue(question, answer)
        score_cap = _score_cap(answer_issue, answer)

        # Parse dimension scores
        scores = []
        seen_dimensions = set()
        for s in data.get("dimension_scores", []):
            if s.get("dimension") in self.session.active_dimensions:
                dimension = s["dimension"]
                seen_dimensions.add(dimension)
                raw_score = float(s.get("score", 5.0))
                score = min(raw_score, score_cap) if score_cap is not None else raw_score
                scores.append(DimensionScore(
                    dimension=dimension,
                    score=score,
                    feedback=_actionable_feedback(
                        s.get("feedback", ""),
                        dimension,
                        self.language,
                        answer,
                        answer_issue,
                    ),
                ))
        for dimension in self.session.active_dimensions:
            if dimension not in seen_dimensions:
                fallback_score = 3.0 if answer.strip() else 0.0
                if score_cap is not None:
                    fallback_score = min(fallback_score, score_cap)
                scores.append(DimensionScore(
                    dimension=dimension,
                    score=fallback_score,
                    feedback=_actionable_feedback("", dimension, self.language, answer, answer_issue),
                ))

        overall = float(data.get("overall_score", sum(s.score for s in scores) / max(len(scores), 1)))
        if score_cap is not None:
            overall = min(overall, score_cap)
        forced_reason = _forced_probe_reason(question, answer, self.language) if probe_allowed else None
        is_triggered = (bool(data.get("is_probe_triggered", False)) or bool(forced_reason)) and probe_allowed
        if answer_issue == "refusal":
            is_triggered = False
        probe_reason = forced_reason or data.get("probe_reason")

        result = EvaluationResult(
            question_index=question_index,
            question_text=question,
            answer_transcript=answer,
            dimension_scores=scores,
            overall_score=overall,
            is_probe=is_probe_question,
            is_probe_triggered=is_triggered,
            probe_reason=probe_reason,
        )

        profile_update = data.get("profile_update", {})
        return result, profile_update
