import json

from fastapi.testclient import TestClient

from web import app as app_module
from web.repositories.json_weekly_report_snapshot_repository import (
    JsonWeeklyReportSnapshotRepository,
)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def reports_client(monkeypatch, snapshot_path):
    def repository_factory():
        return JsonWeeklyReportSnapshotRepository(snapshot_path)

    monkeypatch.setattr(
        app_module,
        "get_report_snapshot_repository",
        repository_factory,
    )
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
):
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
        "warnings": ["Review source coverage."],
        "source_run": {"run_id": snapshot_id},
        "article_count": 3,
        "core_article_count": 1,
        "useful_article_count": 2,
        "excluded_article_count": 0,
        "files": {},
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
