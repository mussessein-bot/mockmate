from datetime import datetime
from app.storage.database import get_db
from app.core.models import InterviewSession
from app.core.exceptions import SessionNotFoundError


async def save_session(session: InterviewSession) -> None:
    session.updated_at = datetime.utcnow()
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO sessions (session_id, data, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (
                session.session_id,
                session.model_dump_json(),
                session.created_at.isoformat(),
                session.updated_at.isoformat(),
            ),
        )
        await db.commit()


async def load_session(session_id: str) -> InterviewSession:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT data FROM sessions WHERE session_id = ?", (session_id,)
        )
        row = await cursor.fetchone()
    if row is None:
        raise SessionNotFoundError(f"Session {session_id} not found")
    return InterviewSession.model_validate_json(row["data"])


async def delete_session(session_id: str) -> None:
    async with get_db() as db:
        await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await db.commit()


async def list_sessions() -> list[dict]:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT session_id, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]
