from web.services.pipeline_run_collection_summary import (
    build_pipeline_run_collection_summary,
)


def run_record(
    run_id,
    workflow_status="pass",
    quality_status="pass",
    quality_score=90,
    warnings=None,
    errors=None,
    run_outputs=None,
):
    return {
        "run_id": run_id,
        "workflow_status": workflow_status,
        "quality_status": quality_status,
        "quality_score": quality_score,
        "warnings": warnings if warnings is not None else [],
        "errors": errors if errors is not None else [],
        "run_outputs": run_outputs if run_outputs is not None else {},
    }


def test_collection_summary_handles_empty_runs():
    summary = build_pipeline_run_collection_summary([])

    assert summary["total_runs"] == 0
    assert summary["latest_run"] is None
    assert summary["failed_count"] == 0
    assert summary["needs_attention_count"] == 0
    assert summary["healthy_count"] == 0
    assert summary["unknown_count"] == 0
    assert summary["average_quality_score"] is None
    assert summary["missing_output_count"] == 0


def test_collection_summary_uses_first_run_as_latest_run():
    runs = [
        run_record("newest-run"),
        run_record("older-run"),
    ]

    summary = build_pipeline_run_collection_summary(runs)

    assert summary["latest_run"] == runs[0]


def test_collection_summary_counts_assessments():
    runs = [
        run_record("healthy-run"),
        run_record(
            "failed-run",
            workflow_status="fail",
            quality_status="warning",
        ),
        run_record(
            "attention-run",
            quality_status="warning",
        ),
        run_record(
            "unknown-run",
            workflow_status="unknown",
            quality_status="unknown",
            quality_score=None,
        ),
    ]

    summary = build_pipeline_run_collection_summary(runs)

    assert summary["total_runs"] == 4
    assert summary["healthy_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["needs_attention_count"] == 1
    assert summary["unknown_count"] == 1


def test_collection_summary_average_quality_score_uses_numeric_scores_only():
    runs = [
        run_record("score-90", quality_score=90),
        run_record("score-80", quality_score=80),
        run_record("score-string", quality_score="70"),
        run_record("score-bool", quality_score=True),
        run_record("score-none", quality_score=None),
    ]

    summary = build_pipeline_run_collection_summary(runs)

    assert summary["average_quality_score"] == 85.0


def test_collection_summary_average_quality_score_is_none_without_numeric_scores():
    runs = [
        run_record("score-string", quality_score="90"),
        run_record("score-none", quality_score=None),
        run_record("score-bool", quality_score=False),
    ]

    summary = build_pipeline_run_collection_summary(runs)

    assert summary["average_quality_score"] is None


def test_collection_summary_sums_missing_output_count():
    runs = [
        run_record(
            "one-missing-run",
            run_outputs={
                "slide_draft": {
                    "path": "outputs/runs/run-1/slide_draft.md",
                    "status": "missing",
                }
            },
        ),
        run_record(
            "two-missing-run",
            run_outputs={
                "copy_ready_report": {
                    "path": "outputs/runs/run-2/copy_ready_report.md",
                    "available": False,
                },
                "output_quality_review": {
                    "path": "outputs/runs/run-2/output_quality_review.md",
                    "status": "failed",
                },
                "market_analysis_report": (
                    "outputs/runs/run-2/market_analysis_report.md"
                ),
            },
        ),
    ]

    summary = build_pipeline_run_collection_summary(runs)

    assert summary["missing_output_count"] == 3
