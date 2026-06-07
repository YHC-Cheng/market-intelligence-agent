import json

import pytest

from web.repositories.json_weekly_report_snapshot_repository import (
    JsonWeeklyReportSnapshotRepository,
)
from web.services.weekly_report_snapshot_writer import (
    RunSummaryNotFoundError,
    WeeklyReportSnapshotWriter,
)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_run_summary(run_dir, run_id, topic="FinOps", report_type=None):
    summary = {
        "run_id": run_id,
        "topic": topic,
        "run_mode": "weekly",
        "status": "pass",
        "created_at": "2026-05-16T09:00:00",
        "finished_at": "2026-05-16T09:02:00",
        "quality_status": "pass",
        "quality_score": 90,
        "metrics": {
            "output_type": "standard",
            "ranked_articles": 1,
            "successful_summaries": 1,
        },
        "run_outputs": {
            "market_analysis_report": str(
                run_dir / "market_analysis_report.md"
            ),
            "ranked_sources": str(run_dir / "ranked_sources.md"),
        },
        "warnings": [],
        "errors": [],
    }
    if report_type is not None:
        summary["report_type"] = report_type

    return summary


def write_valid_run(runs_dir, run_id, topic="FinOps", report_type=None):
    run_dir = runs_dir / run_id
    write_text(
        run_dir / "market_analysis_report.md",
        f"# {topic} Weekly Snapshot\n",
    )
    write_text(
        run_dir / "ranked_sources.md",
        "\n".join([
            "# Ranked Sources",
            "",
            "## 1. Useful signal",
            "",
            "- Recommendation: Useful",
            "",
        ]),
    )
    summary = build_run_summary(
        run_dir,
        run_id,
        topic=topic,
        report_type=report_type,
    )
    write_json(run_dir / "run_summary.json", summary)
    return run_dir


def build_writer(tmp_path):
    runs_dir = tmp_path / "outputs" / "runs"
    repository = JsonWeeklyReportSnapshotRepository(
        tmp_path / "data" / "reports" / "weekly_report_snapshots.json"
    )
    return WeeklyReportSnapshotWriter(
        repository=repository,
        runs_dir=runs_dir,
    )


def test_write_snapshot_for_run_creates_and_saves_snapshot(tmp_path):
    writer = build_writer(tmp_path)
    write_valid_run(writer.runs_dir, "2026-05-16_0900_weekly_FinOps")

    snapshot = writer.write_snapshot_for_run(
        "2026-05-16_0900_weekly_FinOps"
    )

    assert snapshot["run_id"] == "2026-05-16_0900_weekly_FinOps"
    assert snapshot["topic"] == "FinOps"
    assert snapshot["report_type"] == "weekly"
    assert snapshot["title"] == "FinOps Weekly Snapshot"
    assert snapshot["files"]["market_analysis_report"]["status"] == "available"
    assert writer.repository.get_by_run_id(
        "2026-05-16_0900_weekly_FinOps"
    )["snapshot_id"] == "2026-05-16_0900_weekly_FinOps"


def test_write_snapshot_for_run_missing_summary_has_clear_error(tmp_path):
    writer = build_writer(tmp_path)

    with pytest.raises(RunSummaryNotFoundError) as exc_info:
        writer.write_snapshot_for_run("missing-run")

    assert "run_summary.json not found for run_id: missing-run" in str(
        exc_info.value
    )


def test_write_snapshot_for_run_upserts_same_run_id(tmp_path):
    writer = build_writer(tmp_path)
    run_id = "2026-05-16_0900_weekly_FinOps"
    write_valid_run(writer.runs_dir, run_id)

    writer.write_snapshot_for_run(run_id)
    write_text(
        writer.runs_dir / run_id / "market_analysis_report.md",
        "# Updated FinOps Weekly Snapshot\n",
    )
    writer.write_snapshot_for_run(run_id)

    snapshots = writer.repository.list_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0]["run_id"] == run_id
    assert snapshots[0]["title"] == "Updated FinOps Weekly Snapshot"


def test_backfill_scans_multiple_run_directories(tmp_path):
    writer = build_writer(tmp_path)
    write_valid_run(
        writer.runs_dir,
        "2026-05-16_0900_weekly_FinOps",
        topic="FinOps",
    )
    write_valid_run(
        writer.runs_dir,
        "2026-05-17_0900_weekly_AI",
        topic="AI",
    )

    result = writer.backfill_snapshots_from_runs()

    assert result == {
        "scanned_count": 2,
        "created_or_updated_count": 2,
        "skipped_count": 0,
        "error_count": 0,
        "errors": [],
    }
    assert len(writer.repository.list_snapshots()) == 2


def test_backfill_skips_run_directory_without_summary(tmp_path):
    writer = build_writer(tmp_path)
    write_valid_run(writer.runs_dir, "2026-05-16_0900_weekly_FinOps")
    (writer.runs_dir / "incomplete-run").mkdir(parents=True)

    result = writer.backfill_snapshots_from_runs()

    assert result["scanned_count"] == 2
    assert result["created_or_updated_count"] == 1
    assert result["skipped_count"] == 1
    assert result["error_count"] == 0
    assert len(writer.repository.list_snapshots()) == 1


def test_backfill_continues_when_single_run_has_bad_data(tmp_path):
    writer = build_writer(tmp_path)
    write_valid_run(writer.runs_dir, "2026-05-16_0900_weekly_FinOps")
    bad_run_dir = writer.runs_dir / "bad-run"
    write_text(bad_run_dir / "run_summary.json", "{bad json")

    result = writer.backfill_snapshots_from_runs()

    assert result["scanned_count"] == 2
    assert result["created_or_updated_count"] == 1
    assert result["skipped_count"] == 0
    assert result["error_count"] == 1
    assert result["errors"][0]["run_id"] == "bad-run"
    assert "run_summary.json" in result["errors"][0]["run_summary_path"]
    assert len(writer.repository.list_snapshots()) == 1


def test_backfill_skips_non_weekly_report_snapshots(tmp_path):
    writer = build_writer(tmp_path)
    write_valid_run(
        writer.runs_dir,
        "2026-05-16_0900_daily_FinOps",
        report_type="daily",
    )

    result = writer.backfill_snapshots_from_runs()

    assert result["scanned_count"] == 1
    assert result["created_or_updated_count"] == 0
    assert result["skipped_count"] == 1
    assert result["error_count"] == 0
    assert writer.repository.list_snapshots() == []
