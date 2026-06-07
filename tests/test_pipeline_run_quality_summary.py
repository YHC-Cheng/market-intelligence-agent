from web.services.pipeline_run_quality_summary import (
    build_pipeline_run_quality_summary,
)


def test_quality_summary_assesses_healthy_run():
    summary = build_pipeline_run_quality_summary({
        "workflow_status": "pass",
        "quality_status": "pass",
        "quality_score": 95,
        "warnings": [],
        "errors": [],
        "run_outputs": {
            "market_analysis_report": {
                "path": "outputs/runs/run-1/market_analysis_report.md",
                "status": "available",
            }
        },
    })

    assert summary["overall_assessment"] == "Healthy"
    assert summary["workflow_status"] == "pass"
    assert summary["quality_status"] == "pass"
    assert summary["quality_score"] == 95
    assert summary["warning_count"] == 0
    assert summary["error_count"] == 0
    assert summary["missing_output_count"] == 0


def test_quality_summary_assesses_failed_workflow():
    summary = build_pipeline_run_quality_summary({
        "workflow_status": "fail",
        "quality_status": "warning",
        "warnings": [],
        "errors": [],
        "run_outputs": {},
    })

    assert summary["overall_assessment"] == "Failed"


def test_quality_summary_assesses_failed_when_errors_exist():
    summary = build_pipeline_run_quality_summary({
        "workflow_status": "pass",
        "quality_status": "pass",
        "errors": ["Workflow failed late."],
    })

    assert summary["overall_assessment"] == "Failed"
    assert summary["error_count"] == 1
    assert summary["errors"] == ["Workflow failed late."]


def test_quality_summary_assesses_needs_attention_for_warning_status():
    summary = build_pipeline_run_quality_summary({
        "workflow_status": "pass",
        "quality_status": "warning",
        "warnings": [],
        "errors": [],
        "run_outputs": {},
    })

    assert summary["overall_assessment"] == "Needs Attention"


def test_quality_summary_assesses_needs_attention_for_warnings():
    summary = build_pipeline_run_quality_summary({
        "workflow_status": "pass",
        "quality_status": "pass",
        "warnings": ["Limited coverage."],
        "errors": [],
        "run_outputs": {},
    })

    assert summary["overall_assessment"] == "Needs Attention"
    assert summary["warning_count"] == 1
    assert summary["warnings"] == ["Limited coverage."]


def test_quality_summary_assesses_needs_attention_for_missing_outputs():
    summary = build_pipeline_run_quality_summary({
        "workflow_status": "pass",
        "quality_status": "pass",
        "warnings": [],
        "errors": [],
        "run_outputs": {
            "slide_draft": {
                "path": "outputs/runs/run-1/slide_draft.md",
                "status": "missing",
            },
            "copy_ready_report": {
                "path": "outputs/runs/run-1/copy_ready_report.md",
                "available": False,
            },
            "market_analysis_report": (
                "outputs/runs/run-1/market_analysis_report.md"
            ),
        },
    })

    assert summary["overall_assessment"] == "Needs Attention"
    assert summary["missing_output_count"] == 2
    assert summary["missing_outputs"] == [
        {
            "key": "slide_draft",
            "label": "Slide Draft",
            "path": "outputs/runs/run-1/slide_draft.md",
            "status": "missing",
        },
        {
            "key": "copy_ready_report",
            "label": "Copy Ready Report",
            "path": "outputs/runs/run-1/copy_ready_report.md",
            "status": "missing",
        },
    ]


def test_quality_summary_assesses_unknown_for_missing_statuses():
    summary = build_pipeline_run_quality_summary({
        "warnings": [],
        "errors": [],
        "run_outputs": {},
    })

    assert summary["overall_assessment"] == "Unknown"
    assert summary["workflow_status"] == "unknown"
    assert summary["quality_status"] == "unknown"


def test_quality_summary_counts_failed_output_status_as_missing():
    summary = build_pipeline_run_quality_summary({
        "workflow_status": "pass",
        "quality_status": "pass",
        "run_outputs": {
            "output_quality_review": {
                "path": "outputs/runs/run-1/output_quality_review.md",
                "status": "failed",
            }
        },
    })

    assert summary["missing_output_count"] == 1
    assert summary["missing_outputs"][0]["status"] == "failed"
