from typing import Optional
from pydantic import BaseModel
from app.core.models import (
    InterviewType, InterviewMode, InterviewInterface, PersonaType, Language,
    InterviewState, EvaluationResult, SessionSummary,
)


class CreateSessionRequest(BaseModel):
    name:                str
    target_role:         str
    target_company:      Optional[str]       = None
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
