from enum import Enum
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class InterviewType(str, Enum):
    BEHAVIORAL = "behavioral"
    TECHNICAL  = "technical"
    GRADUATE   = "graduate"


class InterviewMode(str, Enum):
    PRESET  = "preset"
    DYNAMIC = "dynamic"


class InterviewInterface(str, Enum):
    VOICE = "voice"   # TTS + speech recording
    TEXT  = "text"    # text chat + optional STT


class InterviewState(str, Enum):
    INIT       = "INIT"
    OPENING    = "OPENING"
    BEHAVIORAL = "BEHAVIORAL"
    DEEP_DIVE  = "DEEP_DIVE"
    TECHNICAL  = "TECHNICAL"
    CLOSING    = "CLOSING"
    COMPLETED  = "COMPLETED"


class PersonaType(str, Enum):
    SARAH  = "sarah"
    MARCUS = "marcus"
    ALEX   = "alex"


class Language(str, Enum):
    ZH = "zh"
    EN = "en"


class MessageRole(str, Enum):
    INTERVIEWER = "interviewer"
    CANDIDATE   = "candidate"
    SYSTEM      = "system"


class Message(BaseModel):
    id:        str      = Field(default_factory=lambda: str(uuid.uuid4()))
    role:      MessageRole
    content:   str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata:  dict[str, Any] = Field(default_factory=dict)
    # metadata: is_probe, question_index, state_at_time


class CandidateProfile(BaseModel):
    name:            str
    target_role:     str
    target_company:  Optional[str] = None
    job_description: Optional[str] = None
    resume_text:     Optional[str] = None
    language:        Language      = Language.ZH


class DimensionScore(BaseModel):
    dimension: str
    score:     float  # 0-10
    feedback:  str


class EvaluationResult(BaseModel):
    model_config = {"protected_namespaces": ()}

    question_index:     int
    question_text:      str
    answer_transcript:  str
    dimension_scores:   list[DimensionScore]
    overall_score:      float
    is_probe:           bool = False        # True if this question was a probe
    is_probe_triggered: bool = False        # True if this answer triggers a probe
    probe_reason:       Optional[str] = None
    model_answer:       Optional[str] = None


class SessionSummary(BaseModel):
    total_score:       float
    grade:             str   # 优秀/良好/一般/待提升
    ai_summary:        str
    active_dimensions: list[str]
    radar_data:        dict[str, float]
    dimension_details: dict[str, dict]
    per_question:      list[EvaluationResult]


class InterviewSession(BaseModel):
    session_id:         str           = Field(default_factory=lambda: str(uuid.uuid4()))
    profile:            CandidateProfile
    interview_type:     InterviewType
    interview_mode:     InterviewMode
    interview_interface: InterviewInterface = InterviewInterface.VOICE
    persona:            PersonaType
    state:              InterviewState = InterviewState.INIT
    messages:           list[Message]  = Field(default_factory=list)
    question_count:     int = 0        # main questions only, probes excluded
    max_questions:      int = 8
    probe_count:        int = 0        # total probes used (max 2)
    last_was_probe:     bool = False   # used to block probing a probe answer
    active_dimensions:       list[str] = Field(default_factory=list)
    candidate_profile_json:  dict      = Field(default_factory=dict)
    evaluations:             list[EvaluationResult] = Field(default_factory=list)
    summary:                 Optional[SessionSummary] = None
    interviewer_constraints: list[str] = Field(default_factory=list)
    last_strategy_decision:  dict      = Field(default_factory=dict)
    job_analysis:            dict      = Field(default_factory=dict)
    created_at:         datetime = Field(default_factory=datetime.utcnow)
    updated_at:         datetime = Field(default_factory=datetime.utcnow)
