import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File
from app.api.schemas import (
    RespondRequest, RespondResponse, StartResponse,
    TTSPreviewRequest, TTSPreviewResponse, ReplayAudioResponse, TranscribeResponse,
)
from app.core.models import InterviewSession, InterviewState, Message, MessageRole
from app.core.state_machine import (
    transition_after_answer, apply_probe, apply_question, can_probe
)
from app.core.memory import merge_profile_update
from app.agents.evaluator import EvaluatorAgent
from app.agents.strategy import StrategyAgent
from app.agents.interviewer import InterviewerAgent
from app.services.tts import generate_audio, generate_preview
from app.services.stt import transcribe_audio, STTError
from app.storage.session_store import load_session, save_session
from app.core.exceptions import SessionNotFoundError
from app.config import AUDIO_DIR
import asyncio
import aiofiles

router = APIRouter()

# Track last question text per session (for replay)
_last_question: dict[str, str] = {}
_last_audio_url: dict[str, str] = {}
# Track paused state
_paused: dict[str, bool] = {}


def _audio_url(filename: str) -> str:
    return f"/audio/{filename}"


async def _get_session(session_id: str) -> InterviewSession:
    try:
        return await load_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/interview/{session_id}/start", response_model=StartResponse)
async def start_interview(session_id: str):
    session = await _get_session(session_id)

    if session.state != InterviewState.INIT:
        # Return current state instead of erroring (handles React StrictMode double-invoke)
        return StartResponse(
            interviewer_text=_last_question.get(session_id, ""),
            audio_url=_last_audio_url.get(session_id, ""),
            state=session.state,
            question_count=session.question_count,
            active_dimensions=session.active_dimensions,
        )

    interviewer = InterviewerAgent(session)
    text = await interviewer.generate_opening()

    # Add first question as OPENING
    session.state = InterviewState.OPENING
    apply_question(session)  # question_count = 1

    msg = Message(role=MessageRole.INTERVIEWER, content=text,
                  metadata={"question_index": session.question_count, "state_at_time": session.state.value})
    session.messages.append(msg)
    _last_question[session_id] = text

    audio_file = await generate_audio(text, session.persona.value, session.profile.language.value, session_id)
    _last_audio_url[session_id] = _audio_url(audio_file)
    await save_session(session)

    return StartResponse(
        interviewer_text=text,
        audio_url=_audio_url(audio_file),
        state=session.state,
        question_count=session.question_count,
        active_dimensions=session.active_dimensions,
    )


@router.post("/interview/{session_id}/respond", response_model=RespondResponse)
async def respond(session_id: str, body: RespondRequest):
    session = await _get_session(session_id)

    if session.state in (InterviewState.COMPLETED, InterviewState.INIT):
        raise HTTPException(status_code=400, detail=f"Cannot respond in state {session.state}")

    if _paused.get(session_id):
        raise HTTPException(status_code=400, detail="Interview is paused")

    transcript = body.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="Transcript is empty")

    # Add candidate message
    candidate_msg = Message(
        role=MessageRole.CANDIDATE,
        content=transcript,
        metadata={"question_index": session.question_count, "state_at_time": session.state.value},
    )
    session.messages.append(candidate_msg)

    # Determine last question text for evaluation
    last_q = _last_question.get(session_id, "")
    is_probe_q = session.state == InterviewState.DEEP_DIVE

    # Step 1: Evaluate
    evaluator = EvaluatorAgent(session)
    eval_result, profile_update = await evaluator.evaluate(
        question=last_q,
        answer=transcript,
        question_index=session.question_count,
        is_probe_question=is_probe_q,
    )

    # Update candidate profile
    session.candidate_profile_json = merge_profile_update(
        session.candidate_profile_json, profile_update
    )
    session.evaluations.append(eval_result)

    # Step 2: Strategy
    strategy = StrategyAgent(session)
    decision = await strategy.decide(
        is_probe_triggered=eval_result.is_probe_triggered,
        probe_reason=eval_result.probe_reason,
    )
    next_action = decision["next_action"]
    topic = decision["topic"]

    # Handle "close" → transition to CLOSING
    if next_action == "close":
        session.state = InterviewState.CLOSING
    else:
        # Update state machine
        new_state = transition_after_answer(session, next_action)

        if next_action == "probe":
            apply_probe(session)
        else:
            # Only count non-probe questions on the NEXT question
            pass

        session.state = new_state

    should_end = session.state in (InterviewState.CLOSING, InterviewState.COMPLETED)

    # Step 3: Generate interviewer reply
    interviewer = InterviewerAgent(session)
    is_closing = session.state == InterviewState.CLOSING

    if is_closing:
        reply_text = await interviewer.generate_closing()
        session.state = InterviewState.COMPLETED
    else:
        is_probe = next_action == "probe"
        reply_text = await interviewer.generate_response(
            next_action=next_action,
            topic=topic,
            is_probe=is_probe,
            probe_reason=eval_result.probe_reason,
        )

        # Advance question count for the new (upcoming) question
        if not is_probe:
            apply_question(session)

    # Save interviewer message
    iv_msg = Message(
        role=MessageRole.INTERVIEWER,
        content=reply_text,
        metadata={
            "question_index": session.question_count,
            "state_at_time": session.state.value,
            "is_probe": next_action == "probe",
        },
    )
    session.messages.append(iv_msg)
    _last_question[session_id] = reply_text

    # TTS
    audio_file = await generate_audio(
        reply_text, session.persona.value, session.profile.language.value, session_id
    )

    should_end = session.state in (InterviewState.COMPLETED,)
    await save_session(session)

    return RespondResponse(
        interviewer_text=reply_text,
        audio_url=_audio_url(audio_file),
        state=session.state,
        question_count=session.question_count,
        is_probe=next_action == "probe",
        probe_reason=eval_result.probe_reason,
        active_dimensions=session.active_dimensions,
        evaluation=eval_result,
        should_end=should_end,
    )


@router.post("/interview/{session_id}/pause")
async def pause_interview(session_id: str):
    await _get_session(session_id)
    _paused[session_id] = True
    return {"paused": True}


@router.post("/interview/{session_id}/resume")
async def resume_interview(session_id: str):
    await _get_session(session_id)
    _paused[session_id] = False
    return {"resumed": True}


@router.get("/interview/{session_id}/replay-audio", response_model=ReplayAudioResponse)
async def replay_audio(session_id: str):
    session = await _get_session(session_id)
    # Find most recent interviewer message audio
    from app.services.tts import _current_audio
    filename = _current_audio.get(session_id)
    if not filename or not (AUDIO_DIR / filename).exists():
        raise HTTPException(status_code=404, detail="No audio available")
    return ReplayAudioResponse(audio_url=_audio_url(filename))


@router.post("/tts/preview", response_model=TTSPreviewResponse)
async def tts_preview(body: TTSPreviewRequest):
    filename = await generate_preview(body.persona, body.language)
    return TTSPreviewResponse(audio_url=_audio_url(filename))


@router.post("/interview/{session_id}/transcribe", response_model=TranscribeResponse)
async def transcribe(session_id: str, file: UploadFile = File(...)):
    session = await _get_session(session_id)
    ext = (file.filename or "audio.webm").rsplit(".", 1)[-1].lower()
    filename = f"{session_id}_{uuid.uuid4().hex[:8]}.{ext}"
    save_path = AUDIO_DIR / filename

    async with aiofiles.open(str(save_path), "wb") as f:
        content = await file.read()
        await f.write(content)

    try:
        transcript = await transcribe_audio(filename, session.profile.language.value)
    except STTError as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        # Delay deletion so Volcano can retry downloading if needed
        async def _delayed_delete():
            await asyncio.sleep(30)
            if save_path.exists():
                save_path.unlink()
        asyncio.create_task(_delayed_delete())

    return TranscribeResponse(transcript=transcript)
