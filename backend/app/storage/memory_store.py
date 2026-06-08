import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.storage.database import get_db


def canonical_tags(tags: list[str]) -> str:
    cleaned = sorted({tag.strip() for tag in tags if tag and tag.strip()})
    return json.dumps(cleaned, ensure_ascii=False)


async def upsert_correction_memory(
    session_id: str,
    target_role: str,
    question_text: str,
    tags: list[str],
    note: str | None,
    interview_type: str,
    persona: str,
    question_type: str,
) -> None:
    """Insert a new correction or increment hit_count for a matching memory."""
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat()
    expires_at = (now_dt + timedelta(days=180)).isoformat()
    tags_json = canonical_tags(tags)

    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT id, hit_count, note
            FROM correction_log
            WHERE target_role = ?
              AND interview_type = ?
              AND persona = ?
              AND question_type = ?
              AND tags = ?
              AND (expires_at IS NULL OR expires_at > datetime('now'))
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            """,
            (target_role, interview_type, persona, question_type, tags_json),
        )
        row = await cursor.fetchone()
        if row:
            merged_note = row["note"] or ""
            if note and note not in merged_note:
                merged_note = (merged_note + "\n" + note).strip()
            await db.execute(
                """
                UPDATE correction_log
                SET hit_count = ?, note = ?, question_text = ?, session_id = ?,
                    updated_at = ?, expires_at = ?
                WHERE id = ?
                """,
                (
                    int(row["hit_count"] or 1) + 1,
                    merged_note or None,
                    question_text,
                    session_id,
                    now,
                    expires_at,
                    row["id"],
                ),
            )
        else:
            await db.execute(
                """
                INSERT INTO correction_log (
                    session_id, target_role, question_text, tags, note, created_at,
                    interview_type, persona, question_type, hit_count, expires_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    target_role,
                    question_text,
                    tags_json,
                    note,
                    now,
                    interview_type,
                    persona,
                    question_type,
                    1,
                    expires_at,
                    now,
                ),
            )
        await db.commit()


def job_cache_key(
    interview_type: str,
    target_role: str,
    target_company: str | None = None,
    target_school: str | None = None,
    target_department: str | None = None,
    target_advisor: str | None = None,
    research_direction: str | None = None,
) -> str:
    parts = [
        interview_type,
        target_role,
        target_company or "",
        target_school or "",
        target_department or "",
        target_advisor or "",
        research_direction or "",
    ]
    return "|".join(part.strip().lower() for part in parts)


async def load_job_knowledge(cache_key: str) -> dict[str, Any] | None:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT search_text, extracted_questions, analysis_json
            FROM job_knowledge_cache
            WHERE cache_key = ?
              AND (expires_at IS NULL OR expires_at > datetime('now'))
            """,
            (cache_key,),
        )
        row = await cursor.fetchone()
    if not row:
        return None
    try:
        return {
            "search_text": row["search_text"] or "",
            "extracted_questions": json.loads(row["extracted_questions"]),
            "analysis": json.loads(row["analysis_json"]),
        }
    except Exception:
        return None


async def save_job_knowledge(
    cache_key: str,
    interview_type: str,
    target_role: str,
    analysis: dict[str, Any],
    extracted_questions: list[dict[str, Any]],
    search_text: str = "",
    target_company: str | None = None,
    target_school: str | None = None,
    target_department: str | None = None,
    target_advisor: str | None = None,
    research_direction: str | None = None,
) -> None:
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat()
    expires_at = (now_dt + timedelta(days=7)).isoformat()
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO job_knowledge_cache (
                cache_key, interview_type, target_role, target_company,
                target_school, target_department, target_advisor, research_direction,
                search_text, extracted_questions, analysis_json,
                created_at, updated_at, expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                search_text = excluded.search_text,
                extracted_questions = excluded.extracted_questions,
                analysis_json = excluded.analysis_json,
                updated_at = excluded.updated_at,
                expires_at = excluded.expires_at
            """,
            (
                cache_key,
                interview_type,
                target_role,
                target_company,
                target_school,
                target_department,
                target_advisor,
                research_direction,
                search_text,
                json.dumps(extracted_questions, ensure_ascii=False),
                json.dumps(analysis, ensure_ascii=False),
                now,
                now,
                expires_at,
            ),
        )
        await db.commit()
