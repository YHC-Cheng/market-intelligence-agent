import json

from fastapi.testclient import TestClient

from web import app as app_module
from web.repositories.json_weekly_report_snapshot_repository import (
    JsonWeeklyReportSnapshotRepository,
)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def reports_client(monkeypatch, snapshot_path, output_root=None):
    def repository_factory():
        return JsonWeeklyReportSnapshotRepository(snapshot_path)

    monkeypatch.setattr(
        app_module,
        "get_report_snapshot_repository",
        repository_factory,
    )
    if output_root is not None:
        monkeypatch.setattr(app_module, "REPORT_OUTPUT_FILES_ROOT", output_root)

    return TestClient(app_module.app)


def report_table_body(response_text):
    start = response_text.index('<table class="data-table report-history-table">')
    body_start = response_text.index("<tbody>", start)
    body_end = response_text.index("</tbody>", body_start)
    return response_text[body_start:body_end]


def sidebar_markup(response_text):
    start = response_text.index('<nav class="sidebar-nav">')
    end = response_text.index("</nav>", start)
    return response_text[start:end]


def snapshot(
    snapshot_id,
    title,
    topic,
    generated_at,
    quality_status="pass",
    quality_score=90,
    warnings=None,
    source_run=None,
    files=None,
):
    if warnings is None:
        warnings = ["Review source coverage."]
    if source_run is None:
        source_run = {"run_id": snapshot_id}
    if files is None:
        files = {}

    return {
        "snapshot_id": snapshot_id,
        "run_id": snapshot_id,
        "topic": topic,
        "report_type": "weekly",
        "title": title,
        "created_at": generated_at,
        "generated_at": generated_at,
        "status": "pass",
        "quality_status": quality_status,
        "quality_score": quality_score,
        "warnings": warnings,
        "source_run": source_run,
        "article_count": 3,
        "core_article_count": 1,
        "useful_article_count": 2,
        "excluded_article_count": 0,
        "files": files,
        "manual_override": False,
    }


def test_reports_page_displays_saved_snapshots(tmp_path, monkeypatch):
    snapshot_path = tmp_path / "weekly_report_snapshots.json"
    write_json(
        snapshot_path,
        [
            snapshot(
                "run-1",
                "FinOps Weekly Snapshot",
                "FinOps",
                "2026-05-16T09:03:00",
                quality_status="warning",
                quality_score=85,
            )
        ],
    )
    client = reports_client(monkeypatch, snapshot_path)

    response = client.get("/reports")

    assert response.status_code == 200
    assert "<h1>Report History</h1>" in response.text
    sidebar = sidebar_markup(response.text)
    assert 'href="/reports"' in sidebar
    assert "Reports" in sidebar
    assert 'aria-current="page"' in sidebar
    assert "FinOps Weekly Snapshot" in response.text
    assert "FinOps" in response.text
    assert "warning" in response.text
    assert "85" in response.text
    assert "3" in response.text
    assert "View Detail" in response.text
    assert 'href="/reports/run-1"' in response.text


def test_reports_page_empty_state(tmp_path, monkeypatch):
    client = reports_client(
        monkeypatch,
        tmp_path / "missing_weekly_report_snapshots.json",
    )

    response = client.get("/reports")

    assert response.status_code == 200
    assert "<h1>Report History</h1>" in response.text
    assert "No saved reports yet" in response.text
    assert "Weekly report snapshots will appear here" in response.text
    assert "report-history-table" not in response.text


def test_reports_page_sorts_snapshots_newest_first(tmp_path, monkeypatch):
    snapshot_path = tmp_path / "weekly_report_snapshots.json"
    write_json(
        snapshot_path,
        [
            snapshot(
                "older-run",
                "Older Snapshot",
                "AI",
                "2026-05-15T09:00:00",
            ),
            snapshot(
                "newer-run",
                "Newer Snapshot",
                "FinOps",
                "2026-05-17T09:00:00",
            ),
            snapshot(
                "middle-run",
                "Middle Snapshot",
                "ProductObservation",
                "2026-05-16T09:00:00",
            ),
        ],
    )
    client = reports_client(monkeypatch, snapshot_path)

    response = client.get("/reports")
    table_body = report_table_body(response.text)

    assert table_body.index("Newer Snapshot") < table_body.index("Middle Snapshot")
    assert table_body.index("Middle Snapshot") < table_body.index("Older Snapshot")


def test_report_detail_page_displays_snapshot_metadata(tmp_path, monkeypatch):
    snapshot_path = tmp_path / "weekly_report_snapshots.json"
    write_json(
        snapshot_path,
        [
            snapshot(
                "run-1",
                "FinOps Weekly Snapshot",
                "FinOps",
                "2026-05-16T09:03:00",
                quality_status="warning",
                quality_score=85,
                source_run={
                    "run_id": "run-1",
                    "run_mode": "weekly",
                    "run_summary_path": "outputs/runs/run-1/run_summary.json",
                },
                files={
                    "market_analysis_report": {
                        "path": "outputs/runs/run-1/market_analysis_report.md",
                        "status": "available",
                    },
                    "slide_draft": {
                        "path": "outputs/runs/run-1/slide_draft.md",
                        "status": "missing",
                    },
                },
            )
        ],
    )
    client = reports_client(monkeypatch, snapshot_path)

    response = client.get("/reports/run-1")

    assert response.status_code == 200
    assert "FinOps Weekly Snapshot" in response.text
    assert "FinOps" in response.text
    assert "run-1" in response.text
    assert "warning" in response.text
    assert "85" in response.text
    assert "Review source coverage." in response.text
    assert "Source Run Metadata" in response.text
    assert "run_summary_path" not in response.text
    assert "Run Summary Path" in response.text
    assert "outputs/runs/run-1/run_summary.json" in response.text
    assert "Manual Override" in response.text
    assert "Not enabled" in response.text
    assert 'href="/reports">Back to Reports</a>' in response.text


def test_report_detail_page_shows_no_warnings_empty_source_and_no_files(
    tmp_path,
    monkeypatch,
):
    snapshot_path = tmp_path / "weekly_report_snapshots.json"
    write_json(
        snapshot_path,
        [
            snapshot(
                "run-empty",
                "AI Weekly Snapshot",
                "AI",
                "2026-05-16T09:03:00",
                warnings=[],
                source_run={},
                files={},
            )
        ],
    )
    client = reports_client(monkeypatch, snapshot_path)

    response = client.get("/reports/run-empty")

    assert response.status_code == 200
    assert "No warnings" in response.text
    assert "No source run metadata" in response.text
    assert "No output files recorded" in response.text


def test_report_detail_page_displays_available_and_missing_output_files(
    tmp_path,
    monkeypatch,
):
    snapshot_path = tmp_path / "weekly_report_snapshots.json"
    write_json(
        snapshot_path,
        [
            snapshot(
                "run-files",
                "Output File Snapshot",
                "FinOps",
                "2026-05-16T09:03:00",
                files={
                    "copy_ready_report": {
                        "path": "outputs/runs/run-files/copy_ready_report.md",
                        "status": "available",
                    },
                    "slide_draft": {
                        "path": "outputs/runs/run-files/slide_draft.md",
                        "status": "missing",
                    },
                },
            )
        ],
    )
    client = reports_client(monkeypatch, snapshot_path)

    response = client.get("/reports/run-files")

    assert response.status_code == 200
    assert "Copy Ready Report" in response.text
    assert "copy_ready_report" in response.text
    assert "outputs/runs/run-files/copy_ready_report.md" in response.text
    assert "available" in response.text
    assert "Slide Draft" in response.text
    assert "outputs/runs/run-files/slide_draft.md" in response.text
    assert "missing" in response.text
    assert 'href="/reports/run-files/files/copy_ready_report"' in response.text
    assert (
        'href="/reports/run-files/files/copy_ready_report/download"'
        in response.text
    )
    assert 'href="/reports/run-files/files/slide_draft"' not in response.text
    assert ">Missing</span>" in response.text


def test_report_detail_page_missing_snapshot_returns_404(tmp_path, monkeypatch):
    client = reports_client(
        monkeypatch,
        tmp_path / "missing_weekly_report_snapshots.json",
    )

    response = client.get("/reports/missing-snapshot")

    assert response.status_code == 404


def test_report_file_view_displays_existing_markdown_content(
    tmp_path,
    monkeypatch,
):
    output_root = tmp_path / "outputs" / "runs"
    report_path = output_root / "run-files" / "market_analysis_report.md"
    write_text(report_path, "# Market Report\n\nA useful weekly signal.\n")
    snapshot_path = tmp_path / "weekly_report_snapshots.json"
    write_json(
        snapshot_path,
        [
            snapshot(
                "run-files",
                "Output File Snapshot",
                "FinOps",
                "2026-05-16T09:03:00",
                files={
                    "market_analysis_report": {
                        "path": str(report_path),
                        "status": "available",
                    },
                },
            )
        ],
    )
    client = reports_client(monkeypatch, snapshot_path, output_root=output_root)

    response = client.get("/reports/run-files/files/market_analysis_report")

    assert response.status_code == 200
    assert "Output File Snapshot" in response.text
    assert "Market Analysis Report" in response.text
    assert "market_analysis_report" in response.text
    assert str(report_path) in response.text
    assert "# Market Report" in response.text
    assert "A useful weekly signal." in response.text
    assert 'href="/reports/run-files">Back to Report</a>' in response.text
    assert 'href="/reports/run-files/files/market_analysis_report/download"' in response.text


def test_report_file_download_returns_existing_file(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs" / "runs"
    report_path = output_root / "run-files" / "copy_ready_report.md"
    write_text(report_path, "# Copy Ready\n\nDownload me.\n")
    snapshot_path = tmp_path / "weekly_report_snapshots.json"
    write_json(
        snapshot_path,
        [
            snapshot(
                "run-files",
                "Output File Snapshot",
                "FinOps",
                "2026-05-16T09:03:00",
                files={
                    "copy_ready_report": {
                        "path": str(report_path),
                        "status": "available",
                    },
                },
            )
        ],
    )
    client = reports_client(monkeypatch, snapshot_path, output_root=output_root)

    response = client.get("/reports/run-files/files/copy_ready_report/download")

    assert response.status_code == 200
    assert response.content == b"# Copy Ready\n\nDownload me.\n"
    assert "attachment" in response.headers["content-disposition"]
    assert "copy_ready_report.md" in response.headers["content-disposition"]


def test_report_file_view_missing_snapshot_returns_404(tmp_path, monkeypatch):
    client = reports_client(
        monkeypatch,
        tmp_path / "missing_weekly_report_snapshots.json",
        output_root=tmp_path / "outputs" / "runs",
    )

    response = client.get("/reports/missing/files/market_analysis_report")

    assert response.status_code == 404


def test_report_file_view_missing_file_key_returns_404(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs" / "runs"
    snapshot_path = tmp_path / "weekly_report_snapshots.json"
    write_json(
        snapshot_path,
        [
            snapshot(
                "run-files",
                "Output File Snapshot",
                "FinOps",
                "2026-05-16T09:03:00",
                files={},
            )
        ],
    )
    client = reports_client(monkeypatch, snapshot_path, output_root=output_root)

    response = client.get("/reports/run-files/files/missing_key")

    assert response.status_code == 404


def test_report_file_view_missing_status_returns_404(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs" / "runs"
    report_path = output_root / "run-files" / "slide_draft.md"
    write_text(report_path, "# Slide Draft\n")
    snapshot_path = tmp_path / "weekly_report_snapshots.json"
    write_json(
        snapshot_path,
        [
            snapshot(
                "run-files",
                "Output File Snapshot",
                "FinOps",
                "2026-05-16T09:03:00",
                files={
                    "slide_draft": {
                        "path": str(report_path),
                        "status": "missing",
                    },
                },
            )
        ],
    )
    client = reports_client(monkeypatch, snapshot_path, output_root=output_root)

    response = client.get("/reports/run-files/files/slide_draft")

    assert response.status_code == 404


def test_report_file_view_missing_physical_file_returns_404(
    tmp_path,
    monkeypatch,
):
    output_root = tmp_path / "outputs" / "runs"
    report_path = output_root / "run-files" / "missing_report.md"
    snapshot_path = tmp_path / "weekly_report_snapshots.json"
    write_json(
        snapshot_path,
        [
            snapshot(
                "run-files",
                "Output File Snapshot",
                "FinOps",
                "2026-05-16T09:03:00",
                files={
                    "market_analysis_report": {
                        "path": str(report_path),
                        "status": "available",
                    },
                },
            )
        ],
    )
    client = reports_client(monkeypatch, snapshot_path, output_root=output_root)

    response = client.get("/reports/run-files/files/market_analysis_report")

    assert response.status_code == 404


def test_report_file_view_rejects_path_outside_outputs_runs(
    tmp_path,
    monkeypatch,
):
    output_root = tmp_path / "outputs" / "runs"
    secret_path = tmp_path / "outside.md"
    write_text(secret_path, "Do not read me.\n")
    snapshot_path = tmp_path / "weekly_report_snapshots.json"
    write_json(
        snapshot_path,
        [
            snapshot(
                "run-files",
                "Output File Snapshot",
                "FinOps",
                "2026-05-16T09:03:00",
                files={
                    "market_analysis_report": {
                        "path": str(secret_path),
                        "status": "available",
                    },
                },
            )
        ],
    )
    client = reports_client(monkeypatch, snapshot_path, output_root=output_root)

    response = client.get("/reports/run-files/files/market_analysis_report")

    assert response.status_code == 404
    assert "Do not read me." not in response.text
