import aiosqlite
from contextlib import asynccontextmanager
from pathlib import Path
from app.config import BASE_DIR

DB_PATH = BASE_DIR / "backend" / "mockmate.db"


@asynccontextmanager
async def get_db():
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def init_db():
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                data         TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS correction_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id    TEXT NOT NULL,
                target_role   TEXT NOT NULL,
                question_text TEXT NOT NULL,
                tags          TEXT NOT NULL,
                note          TEXT,
                created_at    TEXT NOT NULL
            )
        """)
        await _ensure_column(db, "correction_log", "interview_type", "TEXT")
        await _ensure_column(db, "correction_log", "persona", "TEXT")
        await _ensure_column(db, "correction_log", "question_type", "TEXT")
        await _ensure_column(db, "correction_log", "hit_count", "INTEGER NOT NULL DEFAULT 1")
        await _ensure_column(db, "correction_log", "expires_at", "TEXT")
        await _ensure_column(db, "correction_log", "updated_at", "TEXT")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS job_knowledge_cache (
                cache_key           TEXT PRIMARY KEY,
                interview_type      TEXT NOT NULL,
                target_role         TEXT NOT NULL,
                target_company      TEXT,
                target_school       TEXT,
                target_department   TEXT,
                target_advisor      TEXT,
                research_direction  TEXT,
                search_text         TEXT,
                extracted_questions TEXT NOT NULL,
                analysis_json       TEXT NOT NULL,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL,
                expires_at          TEXT
            )
        """)
        await db.commit()


async def _ensure_column(db: aiosqlite.Connection, table: str, column: str, column_type: str) -> None:
    cursor = await db.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    existing = {row[1] for row in rows}
    if column not in existing:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
