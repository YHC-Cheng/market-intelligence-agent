import tempfile
import unittest
from pathlib import Path

from utils.knowledge import (
    ensure_json_file,
    load_json,
    save_json,
    update_market_insights,
    update_source_index,
    upsert_article_knowledge,
)


class KnowledgeHelperTest(unittest.TestCase):
    def test_load_json_returns_empty_dict_for_invalid_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"
            path.write_text("{bad", encoding="utf-8")

            self.assertEqual(load_json(str(path)), {})

    def test_ensure_and_save_json_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "knowledge.json"

            ensure_json_file(path)
            save_json(str(path), {"hello": "世界"})

            self.assertEqual(load_json(str(path)), {"hello": "世界"})

    def test_upsert_article_knowledge_preserves_existing_summary_for_repeated(self):
        article = {
            "title": "Article",
            "url": "https://example.com/article",
            "source": "Example",
            "source_category": "market",
            "source_type": "rss",
            "web_mode": None,
            "published_date": "2026-05-14",
            "topic": "AI",
            "first_seen": "2026-05-14",
            "last_seen": "2026-05-14",
            "seen_count": 1,
            "content_hash": "abc",
            "freshness_status": "new",
            "score": 88,
            "recommendation": "Core",
        }
        summary = {
            "summary": "A useful article.",
            "key_points": ["One", "Two"],
            "why_it_matters": "It matters.",
        }
        ranking = {
            "relevance": 5,
            "use_case_clarity": 5,
            "problem_solution_fit": 4,
            "actionability": 4,
            "credibility_novelty": 5,
            "use_case": "Planning",
            "problem_solved": "Prioritization",
            "reason": "Strong source",
        }

        knowledge = upsert_article_knowledge(article, summary, ranking, {})
        repeated_article = {
            **article,
            "last_seen": "2026-05-15",
            "seen_count": 2,
            "freshness_status": "repeated",
        }
        knowledge = upsert_article_knowledge(
            repeated_article,
            {},
            {},
            knowledge,
        )

        entry = knowledge["https://example.com/article"]
        self.assertEqual(entry["summary"], "A useful article.")
        self.assertEqual(entry["summary_status"], "ready")
        self.assertEqual(entry["score"], 88)
        self.assertEqual(entry["seen_count"], 2)
        self.assertEqual(entry["freshness_status"], "repeated")

    def test_upsert_article_knowledge_marks_metadata_only_articles_skipped(self):
        article = {
            "title": "Old article",
            "url": "https://example.com/old",
            "source": "Example",
            "topic": "FinOps",
            "freshness_status": "old",
        }

        knowledge = upsert_article_knowledge(article, {}, {}, {})

        entry = knowledge["https://example.com/old"]
        self.assertEqual(entry["summary_status"], "skipped")
        self.assertEqual(entry["summary"], "")

    def test_upsert_article_knowledge_marks_old_to_extract_article_skipped(self):
        article = {
            "title": "Old article",
            "url": "https://example.com/old",
            "source": "Example",
            "topic": "FinOps",
            "freshness_status": "old",
        }
        existing = {
            "https://example.com/old": {
                "url": "https://example.com/old",
                "summary_status": "to_extract",
            }
        }

        knowledge = upsert_article_knowledge(article, {}, {}, existing)

        entry = knowledge["https://example.com/old"]
        self.assertEqual(entry["summary_status"], "skipped")

    def test_upsert_article_knowledge_marks_summary_errors_failed(self):
        article = {
            "title": "LLM error article",
            "url": "https://example.com/error",
            "source": "Example",
            "topic": "AI",
        }
        summary = {
            "summary": "",
            "error": "quota exceeded",
        }

        knowledge = upsert_article_knowledge(article, summary, {}, {})

        entry = knowledge["https://example.com/error"]
        self.assertEqual(entry["summary_status"], "failed")
        self.assertEqual(entry["failure_reason"], "quota exceeded")

    def test_upsert_article_knowledge_marks_manual_without_summary_to_extract(self):
        article = {
            "title": "Manual article",
            "url": "https://example.com/manual",
            "source_type": "manual",
            "topic": "AI",
        }

        knowledge = upsert_article_knowledge(article, {}, {}, {})

        entry = knowledge["https://example.com/manual"]
        self.assertEqual(entry["summary_status"], "to_extract")

    def test_update_market_insights_excludes_exclude_sources(self):
        ranked_articles = [
            {
                "title": "Core Article",
                "url": "https://example.com/core",
                "source": "Example",
                "recommendation": "Core",
            },
            {
                "title": "Excluded Article",
                "url": "https://example.com/exclude",
                "source": "Example",
                "recommendation": "Exclude",
            },
        ]

        insights = update_market_insights(
            "AI",
            "2026-W20",
            ranked_articles,
            "outputs/reports/market_analysis_report.md",
            "outputs/slides/slide_draft.md",
            {},
        )

        related_sources = insights["AI_2026-W20"]["related_sources"]
        self.assertEqual(len(related_sources), 1)
        self.assertEqual(related_sources[0]["recommendation"], "Core")

    def test_update_source_index_merges_topics(self):
        source_index = {
            "Example": {
                "name": "Example",
                "url": "https://example.com/feed",
                "category": "ai",
                "type": "rss",
                "web_mode": None,
                "topics": ["AI"],
                "last_checked": "2026-05-13T00:00:00",
                "status": "active",
                "last_entries_count": 3,
            }
        }
        sources = [
            {
                "name": "Example",
                "url": "https://example.com/feed",
                "category": "ai",
                "type": "rss",
                "last_entries_count": 5,
            }
        ]

        updated = update_source_index("FinOps", sources, source_index)

        self.assertEqual(updated["Example"]["last_entries_count"], 5)
        self.assertEqual(updated["Example"]["topics"], ["AI", "FinOps"])


if __name__ == "__main__":
    unittest.main()
