import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import main


class FreshnessFlowTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.history_file = Path(self.temp_dir.name) / "processed_articles.json"
        self.original_history_file = main.PROCESSED_HISTORY_FILE
        main.PROCESSED_HISTORY_FILE = self.history_file

    def tearDown(self):
        main.PROCESSED_HISTORY_FILE = self.original_history_file
        self.temp_dir.cleanup()

    def test_static_source_is_extracted_before_repeated_status(self):
        article = {
            "title": "Static Source",
            "url": "https://example.com/static",
            "source": "Static Source",
            "source_category": "product_observation",
            "source_type": "web",
            "web_mode": "static",
            "published_date": "",
            "topic": "ProductObservation",
            "matched_keywords": []
        }

        with patch("main.trafilatura.fetch_url", return_value="<html></html>"):
            with patch(
                "main.trafilatura.extract",
                return_value="same content"
            ) as extract:
                first_clean = main.extract_articles_content([article])
                first_enriched = main.enrich_articles_with_freshness(first_clean)
                second_clean = main.extract_articles_content([article])
                second_enriched = main.enrich_articles_with_freshness(second_clean)

        self.assertEqual(first_enriched[0]["freshness_status"], "new")
        self.assertEqual(second_enriched[0]["freshness_status"], "repeated")
        self.assertEqual(second_enriched[0]["extraction_status"], "success")
        self.assertTrue(second_enriched[0]["content_hash"])
        self.assertEqual(extract.call_count, 2)

    def test_failed_extraction_on_existing_static_source_is_unknown(self):
        article = {
            "title": "Static Source",
            "url": "https://example.com/static",
            "source": "Static Source",
            "source_category": "product_observation",
            "source_type": "web",
            "web_mode": "static",
            "published_date": "",
            "topic": "ProductObservation",
            "matched_keywords": []
        }

        with patch("main.trafilatura.fetch_url", return_value="<html></html>"):
            with patch("main.trafilatura.extract", return_value="same content"):
                first_clean = main.extract_articles_content([article])
                main.enrich_articles_with_freshness(first_clean)

        with patch("main.trafilatura.fetch_url", return_value=""):
            with patch("main.fetch_html", return_value=""):
                second_clean = main.extract_articles_content([article])
                second_enriched = main.enrich_articles_with_freshness(second_clean)

        self.assertEqual(second_enriched[0]["freshness_status"], "unknown")
        self.assertEqual(second_enriched[0]["content_hash"], "")


class NoEligibleReportsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.original_paths = {
            "RAW_OUTPUT_FILE": main.RAW_OUTPUT_FILE,
            "CLEAN_OUTPUT_FILE": main.CLEAN_OUTPUT_FILE,
            "MARKET_BRIEF_FILE": main.MARKET_BRIEF_FILE,
            "RANKED_SOURCES_FILE": main.RANKED_SOURCES_FILE,
            "MARKET_ANALYSIS_REPORT_FILE": main.MARKET_ANALYSIS_REPORT_FILE,
            "SLIDE_DRAFT_FILE": main.SLIDE_DRAFT_FILE,
            "PROCESSED_HISTORY_FILE": main.PROCESSED_HISTORY_FILE,
        }

        main.RAW_OUTPUT_FILE = self.temp_path / "raw_articles.json"
        main.CLEAN_OUTPUT_FILE = self.temp_path / "clean_articles.json"
        main.MARKET_BRIEF_FILE = self.temp_path / "market_brief.md"
        main.RANKED_SOURCES_FILE = self.temp_path / "ranked_sources.md"
        main.MARKET_ANALYSIS_REPORT_FILE = (
            self.temp_path / "market_analysis_report.md"
        )
        main.SLIDE_DRAFT_FILE = self.temp_path / "slide_draft.md"
        main.PROCESSED_HISTORY_FILE = self.temp_path / "processed_articles.json"

    def tearDown(self):
        for name, value in self.original_paths.items():
            setattr(main, name, value)

        self.temp_dir.cleanup()

    def test_no_eligible_articles_writes_fallbacks_without_llm(self):
        raw_article = {
            "title": "Repeated Static Source",
            "url": "https://example.com/static",
            "source": "Static Source",
            "source_category": "product_observation",
            "source_type": "web",
            "web_mode": "static",
            "published_date": "",
            "topic": "ProductObservation",
            "matched_keywords": []
        }
        repeated_article = {
            **raw_article,
            "content": "same content",
            "content_length": 12,
            "extraction_status": "success",
            "content_hash": "abc",
            "freshness_status": "repeated",
            "first_seen": "2026-05-14",
            "last_seen": "2026-05-14",
            "seen_count": 2
        }

        with patch("main.get_resolved_topic", return_value="ProductObservation"):
            with patch("main.load_keywords", return_value=[]):
                with patch(
                    "main.fetch_articles_from_rss",
                    return_value=([raw_article], 1, 0, [])
                ):
                    with patch(
                        "main.extract_articles_content",
                        return_value=[raw_article]
                    ):
                        with patch(
                            "main.enrich_articles_with_freshness",
                            return_value=[repeated_article]
                        ):
                            with patch(
                                "main.ensure_knowledge_files",
                                return_value={
                                    "articles": str(
                                        self.temp_path
                                        / "articles_knowledge.json"
                                    ),
                                    "insights": str(
                                        self.temp_path
                                        / "market_insights.json"
                                    ),
                                    "sources": str(
                                        self.temp_path
                                        / "source_index.json"
                                    )
                                }
                            ):
                                with patch("main.get_llm_provider") as get_provider:
                                    get_provider.side_effect = AssertionError(
                                        "LLM provider should not be initialized"
                                    )
                                    output = StringIO()

                                    with redirect_stdout(output):
                                        main.main()

        self.assertIn(
            "No eligible articles found. Generated fallback reports without "
            "calling LLM.",
            output.getvalue()
        )
        get_provider.assert_not_called()

        self.assertIn(
            "本週沒有新的 eligible articles。",
            main.MARKET_BRIEF_FILE.read_text(encoding="utf-8")
        )
        self.assertIn(
            "本週沒有可評分的新文章。",
            main.RANKED_SOURCES_FILE.read_text(encoding="utf-8")
        )
        report = main.MARKET_ANALYSIS_REPORT_FILE.read_text(encoding="utf-8")
        self.assertIn("# Market Analysis Report: ProductObservation", report)
        self.assertIn("- Repeated: 1", report)
        self.assertIn(
            "核心訊息：本週未觀察到足夠的新市場訊號。",
            main.SLIDE_DRAFT_FILE.read_text(encoding="utf-8")
        )


if __name__ == "__main__":
    unittest.main()
