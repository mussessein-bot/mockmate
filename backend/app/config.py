import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # interview_agent/
load_dotenv(BASE_DIR / ".env")

# LLM
ARK_API_KEY = os.getenv("ARK_API_KEY", "")

# Web Search
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/coding/v3"
ARK_MODEL = "DeepSeek-V4-Flash"

# Volcano Speech (TTS + STT)
VOLCANO_SPEECH_KEY = os.getenv("VOLCANO_SPEECH_KEY", "")
VOLCANO_TTS_WS = "wss://openspeech.bytedance.com/api/v3/tts/unidirectional/stream"
VOLCANO_TTS_RESOURCE = "seed-tts-2.0"
VOLCANO_STT_SUBMIT = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
VOLCANO_STT_QUERY  = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
VOLCANO_STT_RESOURCE = "volc.seedasr.auc"

# Public URL for backend (Volcano STT needs to fetch audio from here)
# For local demo: set to ngrok URL (e.g. https://xxxx.ngrok.io)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

AUDIO_DIR = Path(__file__).resolve().parent.parent / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR}/backend/mockmate.db"

# Volcano TTS voice IDs per persona and language
PERSONA_VOICES: dict[str, dict[str, str]] = {
    "sarah": {
        "zh": "zh_female_vv_uranus_bigtts",    # Vivi 2.0 — warm female
        "en": "en_female_dacey_uranus_bigtts",  # Dacey
    },
    "marcus": {
        "zh": "zh_male_m191_uranus_bigtts",     # 云舟 2.0 — authoritative male
        "en": "en_male_tim_uranus_bigtts",       # Tim
    },
    "alex": {
        "zh": "zh_female_xiaohe_uranus_bigtts", # 小何 2.0 — energetic
        "en": "en_female_stokie_uranus_bigtts",  # Stokie
    },
}

PERSONAS: dict[str, dict] = {
    "sarah": {
        "name": "Sarah Chen",
        "title_zh": "高级HR经理",
        "title_en": "Senior HR Manager",
        "style_zh": "温和引导，鼓励性追问，善于挖掘候选人亮点",
        "style_en": "Warm and encouraging, draws out the best in candidates",
        "probe_style": "That's interesting, could you tell me more about...",
    },
    "marcus": {
        "name": "Marcus Liu",
        "title_zh": "技术总监",
        "title_en": "Tech Director",
        "style_zh": "直接犀利，追问具体细节，对模糊回答零容忍",
        "style_en": "Direct and demanding, zero tolerance for vague answers",
        "probe_style": "But specifically, what did YOU do in that situation?",
    },
    "alex": {
        "name": "Alex Wang",
        "title_zh": "产品VP",
        "title_en": "Product VP",
        "style_zh": "节奏快，不给时间整理，喜欢情景假设题",
        "style_en": "Fast-paced, loves hypotheticals, keeps candidates on their toes",
        "probe_style": "OK, next—what if the timeline was cut by half?",
    },
}
