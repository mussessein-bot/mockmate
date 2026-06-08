import uuid
import json
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from app.api.schemas import (
    RespondRequest, RespondResponse, StartResponse,
    TTSPreviewRequest, TTSPreviewResponse, ReplayAudioResponse, TranscribeResponse,
    CorrectionRequest, CorrectionResponse,
)
from app.core.models import InterviewSession, InterviewState, Message, MessageRole
from app.core.state_machine import (
    transition_after_answer, apply_probe, apply_question, can_probe
)
from app.core.memory import build_topic_coverage_update, merge_profile_update
from app.agents.evaluator import EvaluatorAgent
from app.agents.strategy import StrategyAgent
from app.agents.interviewer import InterviewerAgent
from app.services.tts import generate_audio, generate_preview
from app.services.stt import transcribe_audio, STTError
from app.storage.session_store import load_session, save_session
from app.storage.memory_store import upsert_correction_memory
from app.core.exceptions import SessionNotFoundError
from app.core.models import InterviewInterface
from app.config import AUDIO_DIR
from app.core.exceptions import TTSError
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


def _primary_dimension(eval_result) -> str | None:
    if not eval_result.dimension_scores:
        return None
    return max(eval_result.dimension_scores, key=lambda s: s.score).dimension


def _topic_from_session(session: InterviewSession, question_text: str) -> str:
    topic = session.last_strategy_decision.get("topic")
    if topic:
        return topic
    if session.question_count <= 1:
        return "opening_self_introduction"
    return question_text[:120]


def _question_type_from_session(session: InterviewSession, is_probe_question: bool) -> str:
    if is_probe_question:
        return "probe"
    return session.last_strategy_decision.get("question_type", "opening")


def _record_topic_coverage(session: InterviewSession, eval_result, question_text: str) -> None:
    update = build_topic_coverage_update(
        topic=_topic_from_session(session, question_text),
        dimension=_primary_dimension(eval_result),
        question_type=_question_type_from_session(session, eval_result.is_probe),
        question_index=eval_result.question_index,
        is_probe=eval_result.is_probe,
        score=eval_result.overall_score,
    )
    session.candidate_profile_json = merge_profile_update(session.candidate_profile_json, update)


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

    if session.interview_interface == InterviewInterface.VOICE:
        try:
            audio_file = await generate_audio(text, session.persona.value, session.profile.language.value, session_id)
            audio_url_val = _audio_url(audio_file)
            _last_audio_url[session_id] = audio_url_val
        except TTSError as e:
            raise HTTPException(status_code=502, detail=f"TTS failed: {e}")
    else:
        audio_url_val = ""
    await save_session(session)

    return StartResponse(
        interviewer_text=text,
        audio_url=audio_url_val,
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
    _record_topic_coverage(session, eval_result, last_q)

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
            question_type=decision.get("question_type", "behavioral"),
            dimension_focus=decision.get("dimension_focus"),
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

    # TTS — skip in text mode
    if session.interview_interface == InterviewInterface.VOICE:
        try:
            audio_file = await generate_audio(
                reply_text, session.persona.value, session.profile.language.value, session_id
            )
            respond_audio_url = _audio_url(audio_file)
        except TTSError as e:
            raise HTTPException(status_code=502, detail=f"TTS failed: {e}")
    else:
        respond_audio_url = ""

    should_end = session.state in (InterviewState.COMPLETED,)
    session.last_strategy_decision = {
        "next_action": next_action,
        "topic": topic,
        "question_type": decision.get("question_type", "behavioral"),
        "dimension_focus": decision.get("dimension_focus", []),
        "is_probe": next_action == "probe",
        "probe_reason": eval_result.probe_reason,
    }
    await save_session(session)

    return RespondResponse(
        interviewer_text=reply_text,
        audio_url=respond_audio_url,
        state=session.state,
        question_count=session.question_count,
        is_probe=next_action == "probe",
        probe_reason=eval_result.probe_reason,
        active_dimensions=session.active_dimensions,
        evaluation=eval_result,
        should_end=should_end,
    )


@router.post("/interview/{session_id}/respond/stream")
async def respond_stream(session_id: str, body: RespondRequest):
    """Text-mode only: SSE streaming endpoint.
    Sends a 'meta' event first with evaluation/state data,
    then streams interviewer text chunks, then a 'done' event.
    """
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

    last_q = _last_question.get(session_id, "")
    is_probe_q = session.state == InterviewState.DEEP_DIVE

    _sse_headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

    def _sse_error(msg: str):
        async def _gen():
            yield f"data: {json.dumps({'type': 'error', 'message': msg}, ensure_ascii=False)}\n\n"
        return StreamingResponse(_gen(), media_type="text/event-stream", headers=_sse_headers)

    try:
        # Step 1: Evaluate
        evaluator = EvaluatorAgent(session)
        eval_result, profile_update = await evaluator.evaluate(
            question=last_q,
            answer=transcript,
            question_index=session.question_count,
            is_probe_question=is_probe_q,
        )
        session.candidate_profile_json = merge_profile_update(session.candidate_profile_json, profile_update)
        session.evaluations.append(eval_result)
        _record_topic_coverage(session, eval_result, last_q)

        # Step 2: Strategy
        strategy = StrategyAgent(session)
        decision = await strategy.decide(
            is_probe_triggered=eval_result.is_probe_triggered,
            probe_reason=eval_result.probe_reason,
        )
    except Exception as e:
        import traceback; traceback.print_exc()
        return _sse_error(str(e))

    next_action = decision["next_action"]
    topic = decision["topic"]

    # Step 3: State transition
    if next_action == "close":
        session.state = InterviewState.CLOSING
    else:
        new_state = transition_after_answer(session, next_action)
        if next_action == "probe":
            apply_probe(session)
        session.state = new_state

    is_closing = session.state == InterviewState.CLOSING
    is_probe = next_action == "probe"

    async def event_stream():
        full_text = ""

        # Send metadata first so frontend can update state immediately
        meta = {
            "type": "meta",
            "state": session.state.value,
            "question_count": session.question_count,
            "is_probe": is_probe,
            "probe_reason": eval_result.probe_reason,
            "should_end": is_closing,
            "evaluation": eval_result.model_dump(),
            "active_dimensions": session.active_dimensions,
        }
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"

        # Stream interviewer text
        interviewer = InterviewerAgent(session)
        if is_closing:
            closing_text = await interviewer.generate_closing()
            full_text = closing_text
            yield f"data: {json.dumps({'type': 'chunk', 'text': closing_text}, ensure_ascii=False)}\n\n"
        else:
            async for chunk in interviewer.stream_response(
                next_action=next_action,
                topic=topic,
                is_probe=is_probe,
                probe_reason=eval_result.probe_reason,
                question_type=decision.get("question_type", "behavioral"),
                dimension_focus=decision.get("dimension_focus"),
            ):
                full_text += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk}, ensure_ascii=False)}\n\n"

        # Persist BEFORE sending done so next request always sees updated state
        if is_closing:
            session.state = InterviewState.COMPLETED
        elif not is_probe:
            apply_question(session)

        iv_msg = Message(
            role=MessageRole.INTERVIEWER,
            content=full_text,
            metadata={
                "question_index": session.question_count,
                "state_at_time": session.state.value,
                "is_probe": is_probe,
            },
        )
        session.messages.append(iv_msg)
        _last_question[session_id] = full_text
        session.last_strategy_decision = {
            "next_action": next_action,
            "topic": topic,
            "question_type": decision.get("question_type", "behavioral"),
            "is_probe": is_probe,
            "probe_reason": eval_result.probe_reason,
        }
        await save_session(session)

        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_sse_headers)


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
    from app.services.tts import _current_audio
    filename = _current_audio.get(session_id)
    # Fallback: find the latest audio file for this session on disk
    if not filename or not (AUDIO_DIR / filename).exists():
        matches = sorted(
            AUDIO_DIR.glob(f"{session_id}_*.mp3"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not matches:
            raise HTTPException(status_code=404, detail="No audio available")
        filename = matches[0].name
    return ReplayAudioResponse(audio_url=_audio_url(filename))


@router.post("/tts/preview", response_model=TTSPreviewResponse)
async def tts_preview(body: TTSPreviewRequest):
    try:
        filename = await generate_preview(body.persona, body.language)
    except TTSError as e:
        raise HTTPException(status_code=502, detail=f"TTS failed: {e}")
    return TTSPreviewResponse(audio_url=_audio_url(filename))


@router.post("/interview/{session_id}/correction", response_model=CorrectionResponse)
async def correct_question(session_id: str, body: CorrectionRequest):
    session = await _get_session(session_id)

    if session.state in (InterviewState.COMPLETED, InterviewState.INIT):
        raise HTTPException(status_code=400, detail=f"Cannot correct in state {session.state}")

    # Find and remove the last INTERVIEWER message (the current pending question)
    last_iv_idx = next(
        (i for i in range(len(session.messages) - 1, -1, -1)
         if session.messages[i].role == MessageRole.INTERVIEWER),
        None,
    )
    if last_iv_idx is None:
        raise HTTPException(status_code=400, detail="No interviewer question to correct")

    bad_question = session.messages[last_iv_idx].content
    session.messages.pop(last_iv_idx)

    # Build constraint from this correction and add to session constraints
    tag_str = "、".join(body.tags)
    constraint = f"问题「{bad_question[:60]}{'…' if len(bad_question) > 60 else ''}」被标记为：{tag_str}"
    if body.note:
        constraint += f"（补充说明：{body.note}）"
    session.interviewer_constraints.append(constraint)

    # Persist to correction_log for cross-session RLHF
    sd = session.last_strategy_decision
    question_type_for_log = sd.get("question_type", "opening")
    await upsert_correction_memory(
        session_id=session_id,
        target_role=session.profile.target_role,
        question_text=bad_question,
        tags=body.tags,
        note=body.note,
        interview_type=session.interview_type.value,
        persona=session.persona.value,
        question_type=question_type_for_log,
    )

    # Re-generate question using saved strategy decision (or fallback defaults)
    next_action = sd.get("next_action", "continue")
    topic = sd.get("topic", session.profile.target_role)
    question_type = sd.get("question_type", "behavioral")
    is_probe = sd.get("is_probe", False)
    probe_reason = sd.get("probe_reason")
    dimension_focus = sd.get("dimension_focus")

    # Don't re-apply probe/question count — this is a replacement, not a new step
    interviewer = InterviewerAgent(session)
    new_text = await interviewer.generate_response(
        next_action=next_action,
        topic=topic,
        is_probe=is_probe,
        probe_reason=probe_reason,
        question_type=question_type,
        dimension_focus=dimension_focus,
    )

    # Append new question to history
    iv_msg = Message(
        role=MessageRole.INTERVIEWER,
        content=new_text,
        metadata={
            "question_index": session.question_count,
            "state_at_time": session.state.value,
            "is_probe": is_probe,
            "is_replacement": True,
        },
    )
    session.messages.append(iv_msg)
    _last_question[session_id] = new_text

    # TTS — skip in text mode
    if session.interview_interface == InterviewInterface.VOICE:
        try:
            audio_file = await generate_audio(
                new_text, session.persona.value, session.profile.language.value, session_id
            )
            audio_url_val = _audio_url(audio_file)
        except TTSError as e:
            raise HTTPException(status_code=502, detail=f"TTS failed: {e}")
    else:
        audio_url_val = ""

    await save_session(session)

    return CorrectionResponse(
        new_question=new_text,
        audio_url=audio_url_val,
        question_count=session.question_count,
    )


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
