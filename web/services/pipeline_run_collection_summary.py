from web.services.pipeline_run_quality_summary import (
    build_pipeline_run_quality_summary,
)


def build_pipeline_run_collection_summary(runs):
    run_list = runs if isinstance(runs, list) else []
    quality_summaries = [
        build_pipeline_run_quality_summary(run)
        for run in run_list
    ]
    numeric_scores = [
        run.get("quality_score")
        for run in run_list
        if is_numeric_score(run.get("quality_score"))
    ]

    return {
        "total_runs": len(run_list),
        "latest_run": run_list[0] if run_list else None,
        "failed_count": count_assessment(quality_summaries, "Failed"),
        "needs_attention_count": count_assessment(
            quality_summaries,
            "Needs Attention",
        ),
        "healthy_count": count_assessment(quality_summaries, "Healthy"),
        "unknown_count": count_assessment(quality_summaries, "Unknown"),
        "average_quality_score": average_score(numeric_scores),
        "missing_output_count": sum(
            summary.get("missing_output_count", 0)
            for summary in quality_summaries
        ),
    }


def count_assessment(quality_summaries, assessment):
    return sum(
        1
        for summary in quality_summaries
        if summary.get("overall_assessment") == assessment
    )


def is_numeric_score(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def average_score(scores):
    if not scores:
        return None

    return round(sum(scores) / len(scores), 1)
