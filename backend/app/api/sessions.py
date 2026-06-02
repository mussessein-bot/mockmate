import json
from fastapi import APIRouter, HTTPException
from app.api.schemas import CreateSessionRequest, CreateSessionResponse
from app.core.models import InterviewSession, CandidateProfile
from app.core.dimensions import DEFAULT_DIMENSIONS
from app.core.memory import init_profile
from app.storage.session_store import save_session, load_session, delete_session
from app.storage.database import get_db
from app.core.exceptions import SessionNotFoundError

router = APIRouter()


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(body: CreateSessionRequest):
    profile = CandidateProfile(
        name=body.name,
        target_role=body.target_role,
        target_company=body.target_company,
        resume_text=body.resume_text,
        language=body.language,
    )
    active_dims = DEFAULT_DIMENSIONS.get(body.interview_type.value, DEFAULT_DIMENSIONS["behavioral"])

    # Load historical corrections for this role (cross-session RLHF)
    historical_constraints: list[str] = []
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT tags, note FROM correction_log WHERE target_role = ? ORDER BY created_at DESC LIMIT 15",
            (body.target_role,),
        )
        rows = await cursor.fetchall()
    if rows:
        tag_counts: dict[str, int] = {}
        for row in rows:
            for tag in json.loads(row["tags"]):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        summary = "、".join(f"{tag}（{cnt}次）" for tag, cnt in tag_counts.items())
        historical_constraints.append(
            f"历史用户对「{body.target_role}」岗位面试的反馈：请避免出现以下类型的问题：{summary}"
        )

    session = InterviewSession(
        profile=profile,
        interview_type=body.interview_type,
        interview_mode=body.interview_mode,
        interview_interface=body.interview_interface,
        persona=body.persona,
        active_dimensions=active_dims,
        candidate_profile_json=init_profile(profile),
        max_questions=8 if body.interview_mode.value == "preset" else 12,
        interviewer_constraints=historical_constraints,
    )
    await save_session(session)
    return CreateSessionResponse(
        session_id=session.session_id,
        state=session.state,
        active_dimensions=session.active_dimensions,
        interview_interface=session.interview_interface,
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    try:
        session = await load_session(session_id)
        return session.model_dump()
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.delete("/sessions/{session_id}")
async def delete_session_route(session_id: str):
    try:
        await delete_session(session_id)
        return {"success": True}
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
