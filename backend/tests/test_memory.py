import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.memory import (  # noqa: E402
    build_topic_coverage_update,
    merge_profile_update,
    normalize_profile,
    profile_to_text,
    topic_coverage_labels,
)
from app.storage import database  # noqa: E402
from app.storage.database import get_db, init_db  # noqa: E402
from app.storage.memory_store import (  # noqa: E402
    canonical_tags,
    job_cache_key,
    load_job_knowledge,
    save_job_knowledge,
    upsert_correction_memory,
)


class MemoryProfileTests(unittest.TestCase):
    def test_normalize_legacy_profile_adds_structured_keys(self):
        profile = normalize_profile({"skills_mentioned": ["Python", "Python"]})

        self.assertEqual(profile["skills_mentioned"], ["Python"])
        self.assertIn("projects", profile)
        self.assertIn("topic_coverage", profile)

    def test_merge_structured_fields_dedupes(self):
        update = {
            "skill_confidence": [
                {"name": "Python", "confidence": 1.5, "evidence": ["built API"], "verified": True},
                {"name": "Python", "confidence": 0.4, "evidence": ["duplicate"]},
            ],
            "projects": [
                {"name": "MockMate", "tech_stack": ["FastAPI", "SQLite"]},
                {"name": "MockMate", "tech_stack": ["Duplicate"]},
            ],
        }

        profile = merge_profile_update({}, update)

        self.assertEqual(len(profile["skill_confidence"]), 1)
        self.assertEqual(profile["skill_confidence"][0]["confidence"], 1.0)
        self.assertTrue(profile["skill_confidence"][0]["verified"])
        self.assertEqual(len(profile["projects"]), 1)

    def test_topic_coverage_labels_prefer_structured_entries(self):
        profile = merge_profile_update(
            {"topics_covered": ["legacy leadership"]},
            build_topic_coverage_update(
                topic="incident response",
                dimension="problem_solving",
                question_type="behavioral",
                question_index=2,
                is_probe=False,
                score=7.5,
            ),
        )

        labels = topic_coverage_labels(profile)

        self.assertTrue(any("incident response" in label for label in labels))
        self.assertTrue(any("dimension=problem_solving" in label for label in labels))
        self.assertIn("legacy leadership", labels)

    def test_profile_to_text_renders_structured_memory(self):
        profile = merge_profile_update(
            {},
            {
                "verified_abilities": [
                    {"name": "structured problem solving", "evidence": ["gave STAR example"]}
                ]
            },
        )

        text = profile_to_text(profile, "en")

        self.assertIn("Verified abilities", text)
        self.assertIn("structured problem solving", text)


class MemoryStoreHelperTests(unittest.TestCase):
    def test_canonical_tags_sorts_and_dedupes(self):
        self.assertEqual(canonical_tags(["too broad", "repeat", "too broad"]), '["repeat", "too broad"]')

    def test_job_cache_key_is_stable(self):
        key1 = job_cache_key("behavioral", " Product Manager ", target_company="Acme")
        key2 = job_cache_key("behavioral", "product manager", target_company=" acme ")

        self.assertEqual(key1, key2)


class MemoryStoreIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = TemporaryDirectory()
        self._old_db_path = database.DB_PATH
        database.DB_PATH = Path(self._tmp.name) / "test.db"
        await init_db()

    async def asyncTearDown(self):
        database.DB_PATH = self._old_db_path
        self._tmp.cleanup()

    async def test_upsert_correction_memory_increments_hit_count(self):
        for session_id in ("s1", "s2"):
            await upsert_correction_memory(
                session_id=session_id,
                target_role="Product Manager",
                question_text="bad question",
                tags=["repeat", "too broad"],
                note="note",
                interview_type="behavioral",
                persona="sarah",
                question_type="behavioral",
            )

        async with get_db() as db:
            cursor = await db.execute("SELECT COUNT(*) AS cnt, MAX(hit_count) AS hits FROM correction_log")
            row = await cursor.fetchone()

        self.assertEqual(row["cnt"], 1)
        self.assertEqual(row["hits"], 2)

    async def test_job_knowledge_cache_round_trip(self):
        key = job_cache_key("behavioral", "Product Manager", target_company="Acme")
        analysis = {
            "core_dimensions": [{"name": "Execution", "description": "Ship work", "weight": "high"}],
            "interview_style": "structured",
            "key_tips": "show impact",
            "summary": "PM interview",
        }
        questions = [{"category": "behavioral", "question": "Tell me about a launch."}]

        await save_job_knowledge(
            cache_key=key,
            interview_type="behavioral",
            target_role="Product Manager",
            target_company="Acme",
            analysis=analysis,
            extracted_questions=questions,
            search_text="search result",
        )
        cached = await load_job_knowledge(key)

        self.assertIsNotNone(cached)
        self.assertEqual(cached["analysis"]["summary"], "PM interview")
        self.assertEqual(cached["extracted_questions"][0]["question"], "Tell me about a launch.")


if __name__ == "__main__":
    unittest.main()
