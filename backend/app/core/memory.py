from app.core.models import CandidateProfile

# Schema for candidate_profile_json stored in InterviewSession
EMPTY_PROFILE: dict = {
    "skills_mentioned":    [],   # e.g. ["Python", "A/B测试"]
    "experiences_summary": [],   # e.g. ["字节1年数据分析"]
    "strengths_observed":  [],   # e.g. ["表达清晰", "有量化习惯"]
    "weak_areas":          [],   # e.g. ["缺乏冲突处理案例"]
    "topics_covered":      [],   # e.g. ["自我介绍", "项目经历"]
    "keywords_to_probe":   [],   # e.g. ["某次项目失败"] — keywords worth probing
}


def init_profile(profile: CandidateProfile) -> dict:
    """Build initial candidate_profile_json from the candidate's setup form."""
    p = dict(EMPTY_PROFILE)
    if profile.resume_text:
        p["experiences_summary"].append(f"简历摘要: {profile.resume_text[:300]}")
    return p


def merge_profile_update(existing: dict, update: dict) -> dict:
    """
    Merge an Evaluator-produced update dict into the existing profile.
    Each key is a list; new items are appended without duplication.
    """
    result = dict(existing)
    for key in EMPTY_PROFILE:
        if key in update and isinstance(update[key], list):
            current = set(result.get(key, []))
            for item in update[key]:
                if item and item not in current:
                    result[key] = result.get(key, []) + [item]
                    current.add(item)
    return result


def profile_to_text(profile_json: dict, language: str = "zh") -> str:
    """Render candidate profile as a readable string for Agent prompts."""
    lines = []
    if profile_json.get("skills_mentioned"):
        label = "Skills mentioned" if language == "en" else "提到的技能"
        lines.append(f"{label}: {', '.join(profile_json['skills_mentioned'])}")
    if profile_json.get("experiences_summary"):
        label = "Experience highlights" if language == "en" else "经历摘要"
        lines.append(f"{label}: {'; '.join(profile_json['experiences_summary'])}")
    if profile_json.get("strengths_observed"):
        label = "Observed strengths" if language == "en" else "已观察到的优势"
        lines.append(f"{label}: {', '.join(profile_json['strengths_observed'])}")
    if profile_json.get("weak_areas"):
        label = "Areas to explore" if language == "en" else "待深挖的弱点"
        lines.append(f"{label}: {', '.join(profile_json['weak_areas'])}")
    if profile_json.get("topics_covered"):
        label = "Topics already covered" if language == "en" else "已覆盖话题"
        lines.append(f"{label}: {', '.join(profile_json['topics_covered'])}")
    if profile_json.get("keywords_to_probe"):
        label = "Keywords worth probing" if language == "en" else "值得追问的关键词"
        lines.append(f"{label}: {', '.join(profile_json['keywords_to_probe'])}")
    return "\n".join(lines) if lines else ("No profile data yet." if language == "en" else "暂无画像数据。")
