from copy import deepcopy
from typing import Any

from app.core.models import CandidateProfile


# Schema for candidate_profile_json stored in InterviewSession.
# Keep legacy string-list fields for existing prompts and sessions, while adding
# structured fields that can carry evidence and confidence.
EMPTY_PROFILE: dict[str, Any] = {
    # Legacy fields consumed by existing prompts.
    "skills_mentioned": [],
    "experiences_summary": [],
    "strengths_observed": [],
    "weak_areas": [],
    "topics_covered": [],
    "keywords_to_probe": [],

    # Structured memory fields.
    "projects": [],
    # [{"name": str, "role": str | None, "tech_stack": [str], "evidence": [...]}]
    "skill_confidence": [],
    # [{"name": str, "confidence": float, "evidence": [...], "verified": bool}]
    "evidence_snippets": [],
    # [{"source": str, "text": str, "question_index": int | None}]
    "verified_abilities": [],
    # [{"name": str, "evidence": [...]}]
    "unverified_abilities": [],
    # [{"name": str, "evidence": [...]}]
    "interviewer_hypotheses": [],
    # [{"hypothesis": str, "evidence": [...], "status": "open|confirmed|rejected"}]
    "topic_coverage": [],
    # [{"topic": str, "dimension": str | None, "question_type": str | None,
    #   "question_index": int | None, "is_probe": bool, "score": float | None}]
}

STRING_LIST_KEYS = {
    "skills_mentioned",
    "experiences_summary",
    "strengths_observed",
    "weak_areas",
    "topics_covered",
    "keywords_to_probe",
}

STRUCTURED_LIST_KEYS = {
    "projects",
    "skill_confidence",
    "evidence_snippets",
    "verified_abilities",
    "unverified_abilities",
    "interviewer_hypotheses",
    "topic_coverage",
}

MAX_STRING_ITEMS = 24
MAX_STRUCTURED_ITEMS = 30
MAX_TEXT_LENGTH = 220


def _truncate(value: Any, limit: int = MAX_TEXT_LENGTH) -> str:
    text = str(value).strip()
    return text[:limit]


def _clean_evidence(evidence: Any) -> list[dict[str, Any]]:
    if not isinstance(evidence, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in evidence:
        if isinstance(item, str):
            text = _truncate(item)
            if text:
                cleaned.append({"source": "answer", "text": text, "question_index": None})
            continue
        if not isinstance(item, dict):
            continue
        text = _truncate(item.get("text", ""))
        if not text:
            continue
        cleaned.append({
            "source": _truncate(item.get("source", "answer"), 40) or "answer",
            "text": text,
            "question_index": item.get("question_index"),
        })
    return cleaned[:5]


def _clean_structured_item(key: str, item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        text = _truncate(item)
        if not text:
            return None
        if key == "evidence_snippets":
            return {"source": "answer", "text": text, "question_index": None}
        if key == "interviewer_hypotheses":
            return {"hypothesis": text, "evidence": [], "status": "open"}
        if key == "topic_coverage":
            return {"topic": text, "dimension": None, "question_type": None,
                    "question_index": None, "is_probe": False, "score": None}
        return {"name": text, "evidence": []}

    if not isinstance(item, dict):
        return None

    if key == "projects":
        name = _truncate(item.get("name", ""))
        if not name:
            return None
        tech_stack = item.get("tech_stack", [])
        return {
            "name": name,
            "role": _truncate(item.get("role", ""), 120) or None,
            "tech_stack": [_truncate(x, 60) for x in tech_stack if _truncate(x, 60)]
            if isinstance(tech_stack, list) else [],
            "evidence": _clean_evidence(item.get("evidence", [])),
        }

    if key == "skill_confidence":
        name = _truncate(item.get("name", ""))
        if not name:
            return None
        try:
            confidence = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = min(1.0, max(0.0, confidence))
        return {
            "name": name,
            "confidence": confidence,
            "evidence": _clean_evidence(item.get("evidence", [])),
            "verified": bool(item.get("verified", False)),
        }

    if key == "evidence_snippets":
        text = _truncate(item.get("text", ""))
        if not text:
            return None
        return {
            "source": _truncate(item.get("source", "answer"), 40) or "answer",
            "text": text,
            "question_index": item.get("question_index"),
        }

    if key in {"verified_abilities", "unverified_abilities"}:
        name = _truncate(item.get("name", ""))
        if not name:
            return None
        return {"name": name, "evidence": _clean_evidence(item.get("evidence", []))}

    if key == "interviewer_hypotheses":
        hypothesis = _truncate(item.get("hypothesis", item.get("name", "")))
        if not hypothesis:
            return None
        status = item.get("status", "open")
        if status not in {"open", "confirmed", "rejected"}:
            status = "open"
        return {
            "hypothesis": hypothesis,
            "evidence": _clean_evidence(item.get("evidence", [])),
            "status": status,
        }

    if key == "topic_coverage":
        topic = _truncate(item.get("topic", ""))
        if not topic:
            return None
        score = item.get("score")
        try:
            score = float(score) if score is not None else None
        except (TypeError, ValueError):
            score = None
        return {
            "topic": topic,
            "dimension": _truncate(item.get("dimension", ""), 80) or None,
            "question_type": _truncate(item.get("question_type", ""), 80) or None,
            "question_index": item.get("question_index"),
            "is_probe": bool(item.get("is_probe", False)),
            "score": score,
        }

    return None


def _dedupe_key(key: str, item: dict[str, Any]) -> tuple[Any, ...]:
    if key == "projects":
        return (item.get("name", "").lower(),)
    if key == "skill_confidence":
        return (item.get("name", "").lower(),)
    if key == "evidence_snippets":
        return (item.get("source"), item.get("text", "").lower())
    if key in {"verified_abilities", "unverified_abilities"}:
        return (item.get("name", "").lower(),)
    if key == "interviewer_hypotheses":
        return (item.get("hypothesis", "").lower(),)
    if key == "topic_coverage":
        return (
            item.get("topic", "").lower(),
            item.get("dimension"),
            item.get("question_type"),
            item.get("question_index"),
            item.get("is_probe"),
        )
    return tuple(sorted(item.items()))


def normalize_profile(profile_json: dict | None) -> dict[str, Any]:
    """Return a profile dict with all memory keys present and sanitized."""
    result = deepcopy(EMPTY_PROFILE)
    if not isinstance(profile_json, dict):
        return result

    for key in STRING_LIST_KEYS:
        values = profile_json.get(key, [])
        if isinstance(values, list):
            seen: set[str] = set()
            cleaned: list[str] = []
            for item in values:
                text = _truncate(item)
                if text and text not in seen:
                    cleaned.append(text)
                    seen.add(text)
            result[key] = cleaned[:MAX_STRING_ITEMS]

    for key in STRUCTURED_LIST_KEYS:
        values = profile_json.get(key, [])
        if not isinstance(values, list):
            continue
        seen: set[tuple[Any, ...]] = set()
        cleaned_items: list[dict[str, Any]] = []
        for item in values:
            cleaned = _clean_structured_item(key, item)
            if not cleaned:
                continue
            marker = _dedupe_key(key, cleaned)
            if marker in seen:
                continue
            cleaned_items.append(cleaned)
            seen.add(marker)
        result[key] = cleaned_items[:MAX_STRUCTURED_ITEMS]

    return result


def init_profile(profile: CandidateProfile) -> dict:
    """Build initial candidate_profile_json from the candidate's setup form."""
    p = normalize_profile(None)
    if profile.resume_text:
        resume_summary = f"Resume summary: {profile.resume_text[:300]}"
        p["experiences_summary"].append(resume_summary)
        p["evidence_snippets"].append({
            "source": "resume",
            "text": profile.resume_text[:MAX_TEXT_LENGTH],
            "question_index": None,
        })
    return p


def merge_profile_update(existing: dict, update: dict) -> dict:
    """
    Merge an Evaluator-produced update dict into the existing profile.
    String-list fields are appended without duplication. Structured fields are
    normalized and deduped by their stable identity.
    """
    result = normalize_profile(existing)
    if not isinstance(update, dict):
        return result

    for key in STRING_LIST_KEYS:
        values = update.get(key, [])
        if not isinstance(values, list):
            continue
        current = set(result.get(key, []))
        for item in values:
            text = _truncate(item)
            if text and text not in current:
                result[key].append(text)
                current.add(text)
        result[key] = result[key][-MAX_STRING_ITEMS:]

    for key in STRUCTURED_LIST_KEYS:
        values = update.get(key, [])
        if not isinstance(values, list):
            continue
        current = {_dedupe_key(key, item) for item in result.get(key, [])}
        for item in values:
            cleaned = _clean_structured_item(key, item)
            if not cleaned:
                continue
            marker = _dedupe_key(key, cleaned)
            if marker in current:
                continue
            result[key].append(cleaned)
            current.add(marker)
        result[key] = result[key][-MAX_STRUCTURED_ITEMS:]

    return result


def build_topic_coverage_update(
    topic: str,
    dimension: str | None,
    question_type: str | None,
    question_index: int | None,
    is_probe: bool,
    score: float | None,
) -> dict[str, list[dict[str, Any]]]:
    """Build a normalized update payload for one answered question."""
    return {
        "topic_coverage": [{
            "topic": topic,
            "dimension": dimension,
            "question_type": question_type,
            "question_index": question_index,
            "is_probe": is_probe,
            "score": score,
        }]
    }


def topic_coverage_labels(profile_json: dict, limit: int = 12) -> list[str]:
    """Return compact topic labels for strategy prompt de-duplication."""
    profile = normalize_profile(profile_json)
    labels: list[str] = []

    for item in profile.get("topic_coverage", [])[-limit:]:
        parts = [item["topic"]]
        if item.get("dimension"):
            parts.append(f"dimension={item['dimension']}")
        if item.get("question_type"):
            parts.append(f"type={item['question_type']}")
        if item.get("score") is not None:
            parts.append(f"score={item['score']:.1f}")
        if item.get("is_probe"):
            parts.append("probe")
        labels.append(" / ".join(parts))

    legacy_topics = profile.get("topics_covered", [])
    for topic in legacy_topics[-limit:]:
        if topic and topic not in labels:
            labels.append(topic)

    return labels[-limit:]


def _format_evidence(evidence: list[dict[str, Any]], limit: int = 1) -> str:
    snippets = []
    for item in evidence[:limit]:
        text = item.get("text")
        if text:
            snippets.append(text)
    return f" evidence: {' | '.join(snippets)}" if snippets else ""


def profile_to_text(profile_json: dict, language: str = "zh") -> str:
    """Render candidate profile as a readable string for Agent prompts."""
    profile = normalize_profile(profile_json)
    lines = []

    labels = {
        "zh": {
            "skills_mentioned": "提到的技能",
            "experiences_summary": "经历摘要",
            "strengths_observed": "已观察到的优势",
            "weak_areas": "待深挖的弱点",
            "topics_covered": "已覆盖话题",
            "keywords_to_probe": "值得追问的关键词",
            "projects": "结构化项目",
            "skill_confidence": "技能置信度",
            "verified_abilities": "已验证能力",
            "unverified_abilities": "未验证能力",
            "interviewer_hypotheses": "待确认假设",
            "topic_coverage": "结构化话题覆盖",
            "empty": "暂无画像数据。",
        },
        "en": {
            "skills_mentioned": "Skills mentioned",
            "experiences_summary": "Experience highlights",
            "strengths_observed": "Observed strengths",
            "weak_areas": "Areas to explore",
            "topics_covered": "Topics already covered",
            "keywords_to_probe": "Keywords worth probing",
            "projects": "Structured projects",
            "skill_confidence": "Skill confidence",
            "verified_abilities": "Verified abilities",
            "unverified_abilities": "Unverified abilities",
            "interviewer_hypotheses": "Open interviewer hypotheses",
            "topic_coverage": "Structured topic coverage",
            "empty": "No profile data yet.",
        },
    }
    lang = labels["en"] if language == "en" else labels["zh"]

    for key in STRING_LIST_KEYS:
        values = profile.get(key, [])
        if values:
            lines.append(f"{lang[key]}: {', '.join(values)}")

    if profile.get("projects"):
        values = []
        for item in profile["projects"][:6]:
            tech = f" ({', '.join(item.get('tech_stack', []))})" if item.get("tech_stack") else ""
            role = f" - {item['role']}" if item.get("role") else ""
            values.append(f"{item['name']}{tech}{role}{_format_evidence(item.get('evidence', []))}")
        lines.append(f"{lang['projects']}: {'; '.join(values)}")

    if profile.get("skill_confidence"):
        values = []
        for item in profile["skill_confidence"][:8]:
            verified = "verified" if item.get("verified") else "unverified"
            values.append(
                f"{item['name']} {item.get('confidence', 0.5):.2f} {verified}"
                f"{_format_evidence(item.get('evidence', []))}"
            )
        lines.append(f"{lang['skill_confidence']}: {'; '.join(values)}")

    for key in ("verified_abilities", "unverified_abilities"):
        values = [
            f"{item['name']}{_format_evidence(item.get('evidence', []))}"
            for item in profile.get(key, [])[:8]
        ]
        if values:
            lines.append(f"{lang[key]}: {'; '.join(values)}")

    if profile.get("interviewer_hypotheses"):
        values = []
        for item in profile["interviewer_hypotheses"][:8]:
            values.append(
                f"{item['hypothesis']} [{item.get('status', 'open')}]"
                f"{_format_evidence(item.get('evidence', []))}"
            )
        lines.append(f"{lang['interviewer_hypotheses']}: {'; '.join(values)}")

    if profile.get("topic_coverage"):
        values = []
        for item in profile["topic_coverage"][:10]:
            parts = [item["topic"]]
            if item.get("dimension"):
                parts.append(f"dimension={item['dimension']}")
            if item.get("question_type"):
                parts.append(f"type={item['question_type']}")
            if item.get("score") is not None:
                parts.append(f"score={item['score']:.1f}")
            if item.get("is_probe"):
                parts.append("probe")
            values.append(" / ".join(parts))
        lines.append(f"{lang['topic_coverage']}: {'; '.join(values)}")

    return "\n".join(lines) if lines else lang["empty"]
