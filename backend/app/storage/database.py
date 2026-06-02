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
        await db.commit()
