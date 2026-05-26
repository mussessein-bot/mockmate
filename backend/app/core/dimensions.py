DIMENSION_POOL: dict[str, dict] = {
    "relevance":     {"name": "相关性",     "name_en": "Relevance",     "weight": 1.0},
    "structure":     {"name": "结构性",     "name_en": "Structure",     "weight": 1.0},
    "specificity":   {"name": "具体性",     "name_en": "Specificity",   "weight": 1.0},
    "impact":        {"name": "影响力",     "name_en": "Impact",        "weight": 1.0},
    "expression":    {"name": "表达清晰度", "name_en": "Expression",    "weight": 1.0},
    "leadership":    {"name": "领导力",     "name_en": "Leadership",    "weight": 1.0},
    "collaboration": {"name": "协作能力",   "name_en": "Collaboration", "weight": 1.0},
    "execution":     {"name": "执行力",     "name_en": "Execution",     "weight": 1.0},
    "resilience":    {"name": "抗压能力",   "name_en": "Resilience",    "weight": 1.0},
    "data_thinking": {"name": "数据思维",   "name_en": "Data Thinking", "weight": 1.0},
    "tech_depth":    {"name": "技术深度",   "name_en": "Tech Depth",    "weight": 1.0},
    "logic":         {"name": "逻辑严密性", "name_en": "Logic",         "weight": 1.0},
    "learning":      {"name": "学习能力",   "name_en": "Learning",      "weight": 1.0},
    "innovation":    {"name": "创新性",     "name_en": "Innovation",    "weight": 1.0},
    "academic":      {"name": "学术潜力",   "name_en": "Academic",      "weight": 1.0},
}

DEFAULT_DIMENSIONS: dict[str, list[str]] = {
    "behavioral": ["relevance", "structure", "specificity", "impact", "expression"],
    "technical":  ["logic", "tech_depth", "specificity", "expression", "data_thinking"],
    "graduate":   ["academic", "logic", "learning", "expression", "relevance"],
}


def get_dimension_name(key: str, language: str = "zh") -> str:
    dim = DIMENSION_POOL.get(key, {})
    return dim.get("name_en" if language == "en" else "name", key)


def get_dimensions_display(keys: list[str], language: str = "zh") -> dict[str, str]:
    return {k: get_dimension_name(k, language) for k in keys if k in DIMENSION_POOL}
