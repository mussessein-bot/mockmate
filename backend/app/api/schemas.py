from typing import Optional
from pydantic import BaseModel
from app.core.models import (
    InterviewType, InterviewMode, InterviewInterface, PersonaType, Language,
    InterviewState, EvaluationResult, SessionSummary,
)


class AnalyzeRoleRequest(BaseModel):
    target_role:     str
    target_company:  Optional[str] = None
    job_description: Optional[str] = None
    interview_type:  Optional[str] = None
    language:        str = "zh"


class RefineAnalysisRequest(BaseModel):
    target_role:     str
    target_company:  Optional[str] = None
    job_description: Optional[str] = None
    user_note:       str
    with_search:     bool = False
    interview_type:  Optional[str] = None
    language:        str = "zh"


class WebSearchAnalyzeRequest(BaseModel):
    interview_type:      str             = "behavioral"
    target_role:         str
    target_company:      Optional[str]   = None
    job_description:     Optional[str]   = None
    # graduate-specific
    target_school:       Optional[str]   = None
    target_department:   Optional[str]   = None
    target_advisor:      Optional[str]   = None
    research_direction:  Optional[str]   = None
    language:            str             = "zh"


class JobAnalysisDimension(BaseModel):
    name:        str
    description: str
    weight:      str  # "高" | "中" | "低"


class JobAnalysisResponse(BaseModel):
    core_dimensions:  list[JobAnalysisDimension]
    interview_style:  str
    key_tips:         str
    summary:          str
    advisor_research_summary: Optional[str] = None


class ExtractedQuestion(BaseModel):
    category: str
    question: str


class WebSearchAnalyzeResponse(BaseModel):
    core_dimensions:     list[JobAnalysisDimension]
    interview_style:     str
    key_tips:            str
    summary:             str
    advisor_research_summary: Optional[str] = None
    extracted_questions: list[ExtractedQuestion] = []
    search_available:    bool = True


class CreateSessionRequest(BaseModel):
    name:                str
    target_role:         str
    target_company:      Optional[str]       = None
    job_description:     Optional[str]       = None
    job_analysis:        Optional[dict]      = None
    resume_text:         Optional[str]       = None
    language:            Language            = Language.ZH
    interview_type:      InterviewType
    interview_mode:      InterviewMode
    interview_interface: InterviewInterface  = InterviewInterface.VOICE
    persona:             PersonaType


class CreateSessionResponse(BaseModel):
    session_id:          str
    state:               InterviewState
    active_dimensions:   list[str]
    interview_interface: InterviewInterface


class RespondRequest(BaseModel):
    transcript: str


class RespondResponse(BaseModel):
    interviewer_text:  str
    audio_url:         str          # empty string when interface=text and TTS not needed
    state:             InterviewState
    question_count:    int
    is_probe:          bool
    probe_reason:      Optional[str]
    active_dimensions: list[str]
    evaluation:        Optional[EvaluationResult]
    should_end:        bool


class StartResponse(BaseModel):
    interviewer_text:  str
    audio_url:         str
    state:             InterviewState
    question_count:    int
    active_dimensions: list[str]


class TranscribeResponse(BaseModel):
    transcript: str


class TTSPreviewRequest(BaseModel):
    persona:  str
    language: str = "zh"


class TTSPreviewResponse(BaseModel):
    audio_url: str


class ReplayAudioResponse(BaseModel):
    audio_url: str


class ParsePDFResponse(BaseModel):
    text: str


class CorrectionRequest(BaseModel):
    tags: list[str]
    note: Optional[str] = None


class CorrectionResponse(BaseModel):
    new_question: str
    audio_url:    str
    question_count: int


class MemorySnapshotResponse(BaseModel):
    candidate_profile:      dict
    topic_coverage:         list[dict]
    topic_labels:           list[str]
    skills_mentioned:       list[str]
    projects:               list[dict]
    interviewer_constraints: list[str]
    active_dimensions:      list[str]
    probe_count:            int
    max_probes:             int = 2
    last_probe_reason:      Optional[str] = None
