import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils import run_manager


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
            source_report.write_text("# Report", encoding="utf-8")
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
                            {"eligible_articles": 2},
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

                        index = json.loads(index_path.read_text(encoding="utf-8"))

            self.assertEqual(summary["status"], "pass")
            self.assertEqual(summary["warnings"], ["non-blocking warning"])
            self.assertEqual(len(index), 1)
            self.assertEqual(
                index[0]["run_id"],
                "2026-05-16_0900_weekly_FinOps",
            )
            self.assertEqual(index[0]["status"], "pass")

    def test_fallback_success_run_records_warning(self):
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
                            "2026-05-16_0900_manual_FinOps",
                            "FinOps",
                            "manual",
                            "2026-05-16T09:00:00",
                            {
                                "output_type": "fallback",
                                "eligible_articles": 0,
                            },
                            {},
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
            self.assertIn(
                "No eligible articles found; fallback report was generated.",
                saved_summary["warnings"],
            )
            self.assertEqual(index[0]["status"], "pass")

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
            self.assertEqual(saved_summary["warnings"], ["warning before failure"])
            self.assertEqual(saved_summary["errors"], ["boom"])


if __name__ == "__main__":
    unittest.main()
