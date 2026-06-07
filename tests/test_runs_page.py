from fastapi.testclient import TestClient

from web import app as app_module


class FakePipelineRunRepository:
    def __init__(self, runs):
        self.runs = runs

    def list_runs(self):
        return self.runs


def runs_client(monkeypatch, runs):
    monkeypatch.setattr(
        app_module,
        "get_pipeline_run_repository",
        lambda: FakePipelineRunRepository(runs),
    )
    return TestClient(app_module.app)


def sidebar_markup(response_text):
    start = response_text.index('<nav class="sidebar-nav">')
    end = response_text.index("</nav>", start)
    return response_text[start:end]


def pipeline_run(
    run_id="2026-05-23_1347_manual_FinOps",
    topic="FinOps",
    run_mode="manual",
    workflow_status="pass",
    quality_status="warning",
    quality_score=85,
    warnings=None,
    errors=None,
):
    if warnings is None:
        warnings = ["Report has limited source coverage."]
    if errors is None:
        errors = ["One output file failed validation."]

    return {
        "run_id": run_id,
        "topic": topic,
        "run_mode": run_mode,
        "created_at": "2026-05-23T13:47:43",
        "generated_at": "2026-05-23T13:48:56",
        "workflow_status": workflow_status,
        "quality_status": quality_status,
        "quality_score": quality_score,
        "warnings": warnings,
        "errors": errors,
        "metrics": {"ranked_articles": 1},
        "run_outputs": {
            "market_analysis_report": (
                "outputs/runs/2026-05-23_1347_manual_FinOps/"
                "market_analysis_report.md"
            )
        },
        "run_summary_path": (
            "outputs/runs/2026-05-23_1347_manual_FinOps/run_summary.json"
        ),
    }


def test_runs_page_displays_pipeline_runs(tmp_path, monkeypatch):
    client = runs_client(
        monkeypatch,
        [
            pipeline_run(
                warnings=[
                    "Limited coverage.",
                    "Only one article was summarized.",
                ],
                errors=["Workflow failed late."],
            )
        ],
    )

    response = client.get("/runs")

    assert response.status_code == 200
    assert "<h1>Run History</h1>" in response.text
    assert "2026-05-23_1347_manual_FinOps" in response.text
    assert "FinOps" in response.text
    assert "manual" in response.text
    assert "2026-05-23T13:48:56" in response.text
    assert "pass" in response.text
    assert "warning" in response.text
    assert "85" in response.text
    assert "<td>2</td>" in response.text
    assert "<td>1</td>" in response.text
    assert "View Detail" in response.text
    assert 'aria-disabled="true"' in response.text


def test_runs_page_empty_state(tmp_path, monkeypatch):
    client = runs_client(monkeypatch, [])

    response = client.get("/runs")

    assert response.status_code == 200
    assert "No pipeline runs found." in response.text
    assert "Run the pipeline locally or make sure outputs/runs exists." in response.text
    assert "run-history-table" not in response.text


def test_runs_page_sidebar_navigation_has_runs_entry(tmp_path, monkeypatch):
    client = runs_client(monkeypatch, [pipeline_run()])

    response = client.get("/runs")
    sidebar = sidebar_markup(response.text)

    assert 'href="/runs"' in sidebar
    assert "Runs" in sidebar
    assert 'aria-current="page"' in sidebar
    assert 'href="/reports"' in sidebar
    assert "Reports" in sidebar
