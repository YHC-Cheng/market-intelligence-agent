import json

from web.models.weekly_report_snapshot import (
    build_weekly_report_snapshot_from_run_summary,
)
from web.repositories.json_weekly_report_snapshot_repository import (
    JsonWeeklyReportSnapshotRepository,
)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_run_summary(run_dir, run_id="2026-05-16_0900_weekly_FinOps"):
    run_outputs = {
        "market_brief": str(run_dir / "market_brief.md"),
        "ranked_sources": str(run_dir / "ranked_sources.md"),
        "market_analysis_report": str(run_dir / "market_analysis_report.md"),
        "slide_draft": str(run_dir / "slide_draft.md"),
        "output_quality_review": str(run_dir / "output_quality_review.md"),
        "review_summary": str(run_dir / "review_summary.md"),
        "copy_ready_report": str(run_dir / "copy_ready_report.md"),
    }
    return {
        "run_id": run_id,
        "topic": "FinOps",
        "run_mode": "weekly",
        "status": "pass",
        "created_at": "2026-05-16T09:00:00",
        "finished_at": "2026-05-16T09:03:00",
        "quality_status": "pass",
        "quality_score": 92,
        "metrics": {
            "output_type": "standard",
            "eligible_articles": 4,
            "ranked_articles": 3,
            "successful_summaries": 3,
        },
        "run_outputs": run_outputs,
        "warnings": ["Check source coverage."],
        "errors": [],
    }


def write_full_run_outputs(run_dir):
    write_text(run_dir / "market_brief.md", "# Market Brief\n")
    write_text(
        run_dir / "ranked_sources.md",
        "\n".join([
            "# Ranked Sources",
            "",
            "## 1. Core signal",
            "",
            "- Recommendation: Core",
            "",
            "## 2. Useful signal",
            "",
            "- Recommendation: Useful",
            "",
            "## 3. Excluded signal",
            "",
            "- Recommendation: Exclude",
            "",
        ]),
    )
    write_text(
        run_dir / "market_analysis_report.md",
        "# FinOps Market Intelligence Report\n",
    )
    write_text(run_dir / "slide_draft.md", "# Slide Draft\n")
    write_text(run_dir / "output_quality_review.md", "# Output Quality Review\n")
    write_text(run_dir / "review_summary.md", "# Review Summary\n")
    write_text(run_dir / "copy_ready_report.md", "# FinOps Weekly Snapshot\n")


def test_build_snapshot_from_complete_run_summary(tmp_path):
    run_dir = tmp_path / "outputs" / "runs" / "2026-05-16_0900_weekly_FinOps"
    write_full_run_outputs(run_dir)
    summary = build_run_summary(run_dir)
    summary_path = run_dir / "run_summary.json"
    summary["run_summary_path"] = str(summary_path)
    write_json(summary_path, summary)

    snapshot = build_weekly_report_snapshot_from_run_summary(summary_path)
    snapshot_data = snapshot.to_dict()

    assert snapshot_data["snapshot_id"] == "2026-05-16_0900_weekly_FinOps"
    assert snapshot_data["run_id"] == "2026-05-16_0900_weekly_FinOps"
    assert snapshot_data["topic"] == "FinOps"
    assert snapshot_data["report_type"] == "weekly"
    assert snapshot_data["title"] == "FinOps Weekly Snapshot"
    assert snapshot_data["created_at"] == "2026-05-16T09:00:00"
    assert snapshot_data["generated_at"] == "2026-05-16T09:03:00"
    assert snapshot_data["status"] == "pass"
    assert snapshot_data["quality_status"] == "pass"
    assert snapshot_data["quality_score"] == 92
    assert snapshot_data["warnings"] == ["Check source coverage."]
    assert snapshot_data["source_run"] == {
        "run_id": "2026-05-16_0900_weekly_FinOps",
        "run_mode": "weekly",
        "run_summary_path": str(summary_path),
    }
    assert snapshot_data["article_count"] == 3
    assert snapshot_data["core_article_count"] == 1
    assert snapshot_data["useful_article_count"] == 1
    assert snapshot_data["excluded_article_count"] == 1
    assert snapshot_data["manual_override"] is False
    assert snapshot_data["files"]["market_analysis_report"]["status"] == "available"
    assert snapshot_data["files"]["run_summary"]["status"] == "available"


def test_build_snapshot_handles_missing_output_files(tmp_path):
    run_dir = tmp_path / "outputs" / "runs" / "2026-05-16_0900_weekly_FinOps"
    write_text(
        run_dir / "market_analysis_report.md",
        "# FinOps Market Intelligence Report\n",
    )
    summary = build_run_summary(run_dir)
    summary_path = run_dir / "run_summary.json"
    summary["run_summary_path"] = str(summary_path)
    write_json(summary_path, summary)

    snapshot = build_weekly_report_snapshot_from_run_summary(summary_path)
    snapshot_data = snapshot.to_dict()

    assert snapshot_data["title"] == "FinOps Market Intelligence Report"
    assert snapshot_data["article_count"] == 3
    assert snapshot_data["core_article_count"] == 0
    assert snapshot_data["useful_article_count"] == 0
    assert snapshot_data["excluded_article_count"] == 0
    assert snapshot_data["files"]["market_analysis_report"]["status"] == "available"
    assert snapshot_data["files"]["ranked_sources"]["status"] == "missing"
    assert snapshot_data["files"]["ranked_sources"]["path"] == str(
        run_dir / "ranked_sources.md"
    )
    assert snapshot_data["files"]["copy_ready_report"]["status"] == "missing"


def test_repository_can_save_list_and_get_snapshots(tmp_path):
    snapshot_path = tmp_path / "data" / "reports" / "weekly_report_snapshots.json"
    repository = JsonWeeklyReportSnapshotRepository(snapshot_path)
    first = {
        "snapshot_id": "snapshot-1",
        "run_id": "run-1",
        "topic": "AI",
        "report_type": "weekly",
        "title": "AI Weekly Report",
        "created_at": "2026-05-16T09:00:00",
        "generated_at": "2026-05-16T09:05:00",
        "status": "pass",
        "quality_status": "pass",
        "quality_score": 91,
        "warnings": [],
        "source_run": {"run_id": "run-1"},
        "article_count": 2,
        "core_article_count": 1,
        "useful_article_count": 1,
        "excluded_article_count": 0,
        "files": {},
        "manual_override": False,
    }
    second = {
        **first,
        "snapshot_id": "snapshot-2",
        "run_id": "run-2",
        "topic": "FinOps",
        "generated_at": "2026-05-17T09:05:00",
    }

    repository.save_snapshot(first)
    repository.save_snapshot(second)

    snapshots = repository.list_snapshots()
    assert [snapshot["snapshot_id"] for snapshot in snapshots] == [
        "snapshot-2",
        "snapshot-1",
    ]
    assert repository.get_snapshot("snapshot-1")["run_id"] == "run-1"
    assert repository.get_by_run_id("run-2")["snapshot_id"] == "snapshot-2"
    assert repository.list_snapshots(topic="AI")[0]["snapshot_id"] == "snapshot-1"
    assert len(read_json(snapshot_path)) == 2


def test_repository_does_not_duplicate_same_snapshot_or_run_id(tmp_path):
    snapshot_path = tmp_path / "weekly_report_snapshots.json"
    repository = JsonWeeklyReportSnapshotRepository(snapshot_path)
    snapshot = {
        "snapshot_id": "snapshot-1",
        "run_id": "run-1",
        "topic": "AI",
        "report_type": "weekly",
        "title": "Original",
        "created_at": "2026-05-16T09:00:00",
        "generated_at": "2026-05-16T09:05:00",
        "status": "pass",
        "quality_status": "pass",
        "quality_score": 91,
        "warnings": [],
        "source_run": {"run_id": "run-1"},
        "article_count": 1,
        "core_article_count": 1,
        "useful_article_count": 0,
        "excluded_article_count": 0,
        "files": {},
        "manual_override": False,
    }

    repository.save_snapshot(snapshot)
    repository.save_snapshot({**snapshot, "title": "Updated"})
    repository.save_snapshot({
        **snapshot,
        "snapshot_id": "snapshot-renamed",
        "title": "Updated again",
    })

    snapshots = repository.list_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0]["snapshot_id"] == "snapshot-renamed"
    assert snapshots[0]["title"] == "Updated again"
