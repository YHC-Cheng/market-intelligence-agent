import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils import run_manager


def write_report(path):
    path.write_text(
        "\n".join([
            "# Market Analysis Report: FinOps",
            "",
            "## 1. Market Trend",
            "",
            "FinOps teams are adopting automation for weekly cost governance.",
            "",
            "## 2. Market Pain Point",
            "",
            "Teams still struggle to connect cloud spend signals to product action.",
            "",
            "## 3. Product Implication",
            "",
            "Products should surface cost anomalies in existing workflows.",
            "",
        ]),
        encoding="utf-8",
    )


class RunManagerTest(unittest.TestCase):
    def test_generate_run_id_uses_official_format(self):
        run_id = run_manager.generate_run_id("FinOps", "weekly")

        self.assertRegex(
            run_id,
            r"^\d{4}-\d{2}-\d{2}_\d{4}_weekly_FinOps$"
        )

    def test_mark_run_success_writes_outputs_latest_and_index(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_report = temp_path / "market_analysis_report.md"
            source_slide = temp_path / "slide_draft.md"
            write_report(source_report)
            source_slide.write_text("# Slide", encoding="utf-8")

            with patch.object(run_manager, "RUNS_DIR", temp_path / "runs"):
                with patch.object(run_manager, "LATEST_DIR", temp_path / "latest"):
                    with patch.object(
                        run_manager,
                        "INDEX_FILE",
                        temp_path / "index/report_index.json",
                    ):
                        summary = run_manager.mark_run_success(
                            "2026-05-16_0900_weekly_FinOps",
                            "FinOps",
                            "weekly",
                            "2026-05-16T09:00:00",
                            {
                                "output_type": "standard",
                                "eligible_articles": 3,
                                "ranked_articles": 2,
                                "successful_summaries": 2,
                            },
                            {
                                "market_analysis_report": str(source_report),
                                "slide_draft": str(source_slide),
                            },
                            {},
                            {},
                            ["non-blocking warning"],
                        )

                        run_dir = (
                            temp_path
                            / "runs/2026-05-16_0900_weekly_FinOps"
                        )
                        latest_dir = temp_path / "latest/FinOps"
                        index_path = temp_path / "index/report_index.json"

                        self.assertTrue((run_dir / "run_summary.json").exists())
                        self.assertTrue(
                            (run_dir / "market_analysis_report.md").exists()
                        )
                        self.assertTrue((run_dir / "slide_draft.md").exists())
                        self.assertTrue(
                            (latest_dir / "run_summary.json").exists()
                        )
                        self.assertTrue(
                            (latest_dir / "market_analysis_report.md").exists()
                        )
                        self.assertTrue((run_dir / "review_summary.md").exists())
                        self.assertTrue((run_dir / "copy_ready_report.md").exists())
                        self.assertTrue(
                            (latest_dir / "review_summary.md").exists()
                        )
                        self.assertTrue(
                            (latest_dir / "copy_ready_report.md").exists()
                        )

                        index = json.loads(index_path.read_text(encoding="utf-8"))
                        quality_review = (
                            run_dir / "output_quality_review.md"
                        ).read_text(encoding="utf-8")

            self.assertEqual(summary["status"], "pass")
            self.assertEqual(summary["quality_status"], "pass")
            self.assertEqual(summary["warnings"], ["non-blocking warning"])
            self.assertIn("Quality status: pass", quality_review)
            self.assertIn(
                "This report is ready for review.",
                quality_review,
            )
            self.assertIn("review_summary", summary["run_outputs"])
            self.assertIn("copy_ready_report", summary["run_outputs"])
            self.assertEqual(len(index), 1)
            self.assertEqual(
                index[0]["run_id"],
                "2026-05-16_0900_weekly_FinOps",
            )
            self.assertEqual(index[0]["status"], "pass")
            self.assertEqual(index[0]["quality_status"], "pass")
            self.assertTrue(index[0]["review_summary_path"].endswith(
                "review_summary.md"
            ))
            self.assertTrue(index[0]["copy_ready_report_path"].endswith(
                "copy_ready_report.md"
            ))

    def test_standard_report_with_limited_coverage_is_quality_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_report = temp_path / "market_analysis_report.md"
            write_report(source_report)

            with patch.object(run_manager, "RUNS_DIR", temp_path / "runs"):
                with patch.object(run_manager, "LATEST_DIR", temp_path / "latest"):
                    with patch.object(
                        run_manager,
                        "INDEX_FILE",
                        temp_path / "index/report_index.json",
                    ):
                        summary = run_manager.mark_run_success(
                            "2026-05-16_0900_weekly_FinOps",
                            "FinOps",
                            "weekly",
                            "2026-05-16T09:00:00",
                            {
                                "output_type": "standard",
                                "eligible_articles": 1,
                                "ranked_articles": 1,
                                "successful_summaries": 1,
                            },
                            {"market_analysis_report": str(source_report)},
                            {},
                            {},
                        )

            self.assertEqual(summary["status"], "pass")
            self.assertEqual(summary["quality_status"], "warning")
            self.assertIn(
                "Report has limited source coverage: ranked_articles < 2.",
                summary["warnings"],
            )
            self.assertIn(
                "Only 1 article was summarized; report may not be suitable "
                "for external sharing.",
                summary["warnings"],
            )

    def test_fallback_success_run_records_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_report = temp_path / "market_analysis_report.md"
            source_report.write_text("# Fallback Report", encoding="utf-8")

            with patch.object(run_manager, "RUNS_DIR", temp_path / "runs"):
                with patch.object(run_manager, "LATEST_DIR", temp_path / "latest"):
                    with patch.object(
                        run_manager,
                        "INDEX_FILE",
                        temp_path / "index/report_index.json",
                    ):
                        summary = run_manager.mark_run_success(
                            "2026-05-16_0900_manual_FinOps",
                            "FinOps",
                            "manual",
                            "2026-05-16T09:00:00",
                            {
                                "output_type": "fallback",
                                "eligible_articles": 0,
                                "ranked_articles": 0,
                                "successful_summaries": 0,
                            },
                            {"market_analysis_report": str(source_report)},
                            {},
                            {},
                        )
                        saved_summary = json.loads(
                            Path(summary["run_summary_path"]).read_text(
                                encoding="utf-8"
                            )
                        )
                        index = run_manager.load_report_index()

            self.assertEqual(saved_summary["status"], "pass")
            self.assertEqual(saved_summary["quality_status"], "warning")
            self.assertIn(
                "No eligible articles found; fallback report was generated.",
                saved_summary["warnings"],
            )
            self.assertEqual(
                saved_summary["warnings"].count(
                    "No eligible articles found; fallback report was generated."
                ),
                1,
            )
            self.assertEqual(index[0]["status"], "pass")
            self.assertEqual(index[0]["quality_status"], "warning")

    def test_zero_eligible_success_run_records_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch.object(run_manager, "RUNS_DIR", temp_path / "runs"):
                with patch.object(run_manager, "LATEST_DIR", temp_path / "latest"):
                    with patch.object(
                        run_manager,
                        "INDEX_FILE",
                        temp_path / "index/report_index.json",
                    ):
                        summary = run_manager.mark_run_success(
                            "2026-05-16_0900_manual_AI",
                            "AI",
                            "manual",
                            "2026-05-16T09:00:00",
                            {
                                "output_type": "standard",
                                "eligible_articles": 0,
                            },
                            {},
                            {},
                            {},
                        )

            self.assertIn(
                "No eligible articles found; fallback report was generated.",
                summary["warnings"],
            )

    def test_report_index_updates_existing_run_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch.object(
                run_manager,
                "INDEX_FILE",
                temp_path / "index/report_index.json",
            ):
                entry = {
                    "run_id": "same-run",
                    "topic": "AI",
                    "run_mode": "manual",
                    "created_at": "2026-05-16T09:00:00",
                    "status": "pass",
                    "quality_score": None,
                    "quality_status": None,
                    "report_path": "old",
                    "slide_path": "old",
                    "run_summary_path": "old",
                }
                run_manager.update_report_index(entry)
                entry["report_path"] = "new"
                run_manager.update_report_index(entry)
                index = run_manager.load_report_index()

            self.assertEqual(len(index), 1)
            self.assertEqual(index[0]["report_path"], "new")

    def test_mark_run_failed_records_status_and_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch.object(run_manager, "RUNS_DIR", temp_path / "runs"):
                with patch.object(run_manager, "LATEST_DIR", temp_path / "latest"):
                    with patch.object(
                        run_manager,
                        "INDEX_FILE",
                        temp_path / "index/report_index.json",
                    ):
                        summary = run_manager.mark_run_failed(
                            "2026-05-16_0900_test_AI",
                            "AI",
                            "test",
                            "2026-05-16T09:00:00",
                            {},
                            ["boom"],
                            ["warning before failure"],
                        )
                        summary_path = Path(summary["run_summary_path"])
                        saved_summary = json.loads(
                            summary_path.read_text(encoding="utf-8")
                        )

            self.assertEqual(saved_summary["status"], "fail")
            self.assertEqual(saved_summary["quality_status"], "fail")
            self.assertIn("warning before failure", saved_summary["warnings"])
            self.assertIn(
                "Workflow failed; report is not usable.",
                saved_summary["warnings"],
            )
            self.assertIn(
                "Market analysis report is missing or empty.",
                saved_summary["warnings"],
            )
            self.assertEqual(saved_summary["errors"], ["boom"])

    def test_report_missing_success_run_is_quality_fail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch.object(run_manager, "RUNS_DIR", temp_path / "runs"):
                with patch.object(run_manager, "LATEST_DIR", temp_path / "latest"):
                    with patch.object(
                        run_manager,
                        "INDEX_FILE",
                        temp_path / "index/report_index.json",
                    ):
                        summary = run_manager.mark_run_success(
                            "2026-05-16_0900_test_AI",
                            "AI",
                            "test",
                            "2026-05-16T09:00:00",
                            {
                                "output_type": "standard",
                                "eligible_articles": 3,
                                "ranked_articles": 2,
                                "successful_summaries": 2,
                            },
                            {},
                            {},
                            {},
                        )

            self.assertEqual(summary["status"], "pass")
            self.assertEqual(summary["quality_status"], "fail")
            self.assertIn(
                "Market analysis report is missing or empty.",
                summary["warnings"],
            )


if __name__ == "__main__":
    unittest.main()
