from fastapi.testclient import TestClient

from web import app as app_module


class FakePipelineRunRepository:
    def __init__(self, runs):
        self.runs = runs

    def list_runs(self):
        return self.runs

    def get_run(self, run_id):
        for run in self.runs:
            if run.get("run_id") == run_id:
                return run

        return None

    def get_run_outputs(self, run_id):
        run = self.get_run(run_id)
        if run is None:
            return {}

        return run.get("run_outputs") or {}


def runs_client(monkeypatch, runs, output_root=None):
    monkeypatch.setattr(
        app_module,
        "get_pipeline_run_repository",
        lambda: FakePipelineRunRepository(runs),
    )
    if output_root is not None:
        monkeypatch.setattr(app_module, "RUN_OUTPUT_FILES_ROOT", output_root)

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


def detail_body(response_text):
    start = response_text.index('<div class="detail-layout">')
    return response_text[start:]


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    assert (
        'href="/runs/2026-05-23_1347_manual_FinOps"'
        in response.text
    )
    assert 'aria-disabled="true"' not in response.text


def test_runs_page_view_detail_link_is_url_encoded(tmp_path, monkeypatch):
    client = runs_client(
        monkeypatch,
        [pipeline_run(run_id="manual run: FinOps")],
    )

    response = client.get("/runs")

    assert response.status_code == 200
    assert 'href="/runs/manual%20run%3A%20FinOps"' in response.text


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


def test_run_detail_page_displays_run_metadata(tmp_path, monkeypatch):
    client = runs_client(monkeypatch, [pipeline_run()])

    response = client.get("/runs/2026-05-23_1347_manual_FinOps")

    assert response.status_code == 200
    assert 'href="/runs">Back to Runs</a>' in response.text
    assert "<h1>Run Detail</h1>" in response.text
    assert "2026-05-23_1347_manual_FinOps" in response.text
    assert "FinOps" in response.text
    assert "manual" in response.text
    assert "2026-05-23T13:47:43" in response.text
    assert "2026-05-23T13:48:56" in response.text
    assert "Workflow: pass" in response.text
    assert "Quality: warning" in response.text
    assert "85" in response.text


def test_run_detail_page_quality_summary_displays_healthy_assessment(
    tmp_path,
    monkeypatch,
):
    run = pipeline_run(
        workflow_status="pass",
        quality_status="pass",
        quality_score=96,
        warnings=[],
        errors=[],
    )
    run["run_outputs"] = {
        "market_analysis_report": {
            "path": "outputs/runs/healthy-run/market_analysis_report.md",
            "status": "available",
        }
    }
    client = runs_client(monkeypatch, [run])

    response = client.get("/runs/2026-05-23_1347_manual_FinOps")

    assert response.status_code == 200
    assert "Quality Summary" in response.text
    assert "Overall Assessment" in response.text
    assert "Healthy" in response.text
    assert "Warnings Count" in response.text
    assert "Errors Count" in response.text
    assert "Missing Outputs Count" in response.text
    assert "96" in response.text


def test_run_detail_page_quality_summary_displays_failed_assessment_for_errors(
    tmp_path,
    monkeypatch,
):
    run = pipeline_run(
        workflow_status="pass",
        quality_status="pass",
        warnings=[],
        errors=["Workflow failed late."],
    )
    run["run_outputs"] = {}
    client = runs_client(monkeypatch, [run])

    response = client.get("/runs/2026-05-23_1347_manual_FinOps")

    assert response.status_code == 200
    assert "Failed" in response.text
    assert "Workflow failed late." in response.text


def test_run_detail_page_quality_summary_displays_failed_for_workflow_fail(
    tmp_path,
    monkeypatch,
):
    run = pipeline_run(
        workflow_status="fail",
        quality_status="warning",
        warnings=[],
        errors=[],
    )
    run["run_outputs"] = {}
    client = runs_client(monkeypatch, [run])

    response = client.get("/runs/2026-05-23_1347_manual_FinOps")

    assert response.status_code == 200
    assert "Failed" in response.text


def test_run_detail_page_quality_summary_displays_needs_attention(
    tmp_path,
    monkeypatch,
):
    run = pipeline_run(
        workflow_status="pass",
        quality_status="warning",
        warnings=["Limited coverage."],
        errors=[],
    )
    run["run_outputs"] = {
        "slide_draft": {
            "path": "outputs/runs/run-1/slide_draft.md",
            "status": "missing",
        }
    }
    client = runs_client(monkeypatch, [run])

    response = client.get("/runs/2026-05-23_1347_manual_FinOps")

    assert response.status_code == 200
    assert "Needs Attention" in response.text
    assert "Limited coverage." in response.text
    assert "Slide Draft" in response.text
    assert "slide_draft.md" in response.text


def test_run_detail_page_quality_summary_displays_unknown_assessment(
    tmp_path,
    monkeypatch,
):
    run = pipeline_run(
        workflow_status="unknown",
        quality_status="unknown",
        warnings=[],
        errors=[],
    )
    run["run_outputs"] = {}
    client = runs_client(monkeypatch, [run])

    response = client.get("/runs/2026-05-23_1347_manual_FinOps")

    assert response.status_code == 200
    assert "Unknown" in response.text


def test_run_detail_page_displays_metrics_warnings_errors_and_outputs(
    tmp_path,
    monkeypatch,
):
    run = pipeline_run(
        warnings=["Limited coverage.", "Only one summary."],
        errors=["Workflow failed late."],
    )
    run["metrics"] = {
        "ranked_articles": 1,
        "successful_summaries": 1,
    }
    run["run_outputs"] = {
        "market_analysis_report": (
            "outputs/runs/2026-05-23_1347_manual_FinOps/"
            "market_analysis_report.md"
        ),
        "slide_draft": {
            "path": (
                "outputs/runs/2026-05-23_1347_manual_FinOps/"
                "slide_draft.md"
            ),
            "status": "missing",
        },
    }
    client = runs_client(monkeypatch, [run])

    response = client.get("/runs/2026-05-23_1347_manual_FinOps")
    body = detail_body(response.text)

    assert response.status_code == 200
    assert "Ranked Articles" in body
    assert "Successful Summaries" in body
    assert "Limited coverage." in body
    assert "Only one summary." in body
    assert "Workflow failed late." in body
    assert "Market Analysis Report" in body
    assert "market_analysis_report" in body
    assert "market_analysis_report.md" in body
    assert "Slide Draft" in body
    assert "slide_draft.md" in body
    assert "missing" in body
    assert "Failure Summary" in body
    assert "Missing Outputs" in body


def test_run_detail_page_displays_output_file_actions_for_available_file(
    tmp_path,
    monkeypatch,
):
    output_root = tmp_path / "outputs"
    report_path = (
        output_root
        / "runs"
        / "2026-05-23_1347_manual_FinOps"
        / "market_analysis_report.md"
    )
    write_text(report_path, "# Market report\n")
    run = pipeline_run()
    run["run_outputs"] = {
        "market_analysis_report": str(report_path),
    }
    client = runs_client(monkeypatch, [run], output_root=output_root)

    response = client.get("/runs/2026-05-23_1347_manual_FinOps")

    assert response.status_code == 200
    assert 'href="/runs/2026-05-23_1347_manual_FinOps/files/market_analysis_report"' in response.text
    assert (
        'href="/runs/2026-05-23_1347_manual_FinOps/files/'
        'market_analysis_report/download"'
    ) in response.text


def test_run_detail_page_does_not_show_actions_for_missing_output(
    tmp_path,
    monkeypatch,
):
    output_root = tmp_path / "outputs"
    run = pipeline_run()
    run["run_outputs"] = {
        "slide_draft": {
            "path": str(
                output_root
                / "runs"
                / "2026-05-23_1347_manual_FinOps"
                / "slide_draft.md"
            ),
            "status": "missing",
        },
    }
    client = runs_client(monkeypatch, [run], output_root=output_root)

    response = client.get("/runs/2026-05-23_1347_manual_FinOps")

    assert response.status_code == 200
    assert "slide_draft.md" in response.text
    assert 'files/slide_draft' not in response.text


def test_run_detail_page_displays_empty_warning_error_metric_and_output_states(
    tmp_path,
    monkeypatch,
):
    run = pipeline_run(
        quality_score=None,
        warnings=[],
        errors=[],
    )
    run["metrics"] = {}
    run["run_outputs"] = {}
    client = runs_client(monkeypatch, [run])

    response = client.get("/runs/2026-05-23_1347_manual_FinOps")

    assert response.status_code == 200
    assert "No warnings" in response.text
    assert "No errors" in response.text
    assert "No metrics recorded" in response.text
    assert "No missing output files" in response.text
    assert "No output files recorded" in response.text
    assert "&mdash;" in response.text


def test_run_detail_page_missing_run_returns_404(tmp_path, monkeypatch):
    client = runs_client(monkeypatch, [])

    response = client.get("/runs/missing-run")

    assert response.status_code == 404


def test_run_file_view_displays_existing_text_content(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    report_path = (
        output_root
        / "runs"
        / "2026-05-23_1347_manual_FinOps"
        / "market_analysis_report.md"
    )
    write_text(report_path, "# Market Analysis\n\nPlain markdown content.")
    run = pipeline_run()
    run["run_outputs"] = {
        "market_analysis_report": str(report_path),
    }
    client = runs_client(monkeypatch, [run], output_root=output_root)

    response = client.get(
        "/runs/2026-05-23_1347_manual_FinOps/files/market_analysis_report"
    )

    assert response.status_code == 200
    assert "Market Analysis Report" in response.text
    assert "market_analysis_report" in response.text
    assert str(report_path) in response.text
    assert "# Market Analysis" in response.text
    assert "Plain markdown content." in response.text
    assert (
        'href="/runs/2026-05-23_1347_manual_FinOps/files/'
        'market_analysis_report/download"'
    ) in response.text
    assert 'href="/runs/2026-05-23_1347_manual_FinOps">Back to Run</a>' in response.text


def test_run_file_download_returns_existing_file(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    report_path = (
        output_root
        / "runs"
        / "2026-05-23_1347_manual_FinOps"
        / "copy_ready_report.md"
    )
    write_text(report_path, "# Copy ready\n")
    run = pipeline_run()
    run["run_outputs"] = {
        "copy_ready_report": str(report_path),
    }
    client = runs_client(monkeypatch, [run], output_root=output_root)

    response = client.get(
        "/runs/2026-05-23_1347_manual_FinOps/files/copy_ready_report/download"
    )

    assert response.status_code == 200
    assert response.content == b"# Copy ready\n"
    assert 'filename="copy_ready_report.md"' in response.headers[
        "content-disposition"
    ]


def test_run_file_view_missing_run_returns_404(tmp_path, monkeypatch):
    client = runs_client(monkeypatch, [], output_root=tmp_path / "outputs")

    response = client.get("/runs/missing-run/files/market_analysis_report")

    assert response.status_code == 404


def test_run_file_view_missing_file_key_returns_404(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    run = pipeline_run()
    run["run_outputs"] = {}
    client = runs_client(monkeypatch, [run], output_root=output_root)

    response = client.get(
        "/runs/2026-05-23_1347_manual_FinOps/files/missing_key"
    )

    assert response.status_code == 404


def test_run_file_view_missing_physical_file_returns_404(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    run = pipeline_run()
    run["run_outputs"] = {
        "market_analysis_report": str(
            output_root
            / "runs"
            / "2026-05-23_1347_manual_FinOps"
            / "missing_report.md"
        ),
    }
    client = runs_client(monkeypatch, [run], output_root=output_root)

    response = client.get(
        "/runs/2026-05-23_1347_manual_FinOps/files/market_analysis_report"
    )

    assert response.status_code == 404


def test_run_file_view_rejects_unsafe_path(tmp_path, monkeypatch):
    output_root = tmp_path / "outputs"
    unsafe_path = tmp_path / "secret.md"
    write_text(unsafe_path, "Do not read this.")
    run = pipeline_run()
    run["run_outputs"] = {
        "market_analysis_report": str(unsafe_path),
    }
    client = runs_client(monkeypatch, [run], output_root=output_root)

    response = client.get(
        "/runs/2026-05-23_1347_manual_FinOps/files/market_analysis_report"
    )

    assert response.status_code == 404
    assert "Do not read this." not in response.text
