import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from utils.cache import sanitize_filename


RUNS_DIR = Path("outputs/runs")
LATEST_DIR = Path("outputs/latest")
INDEX_FILE = Path("outputs/index/report_index.json")

STANDARD_OUTPUTS = {
    "market_brief": Path("outputs/reports/market_brief.md"),
    "ranked_sources": Path("outputs/reports/ranked_sources.md"),
    "market_analysis_report": Path("outputs/reports/market_analysis_report.md"),
    "slide_draft": Path("outputs/slides/slide_draft.md"),
    "output_quality_review": Path("outputs/reports/output_quality_review.md"),
}

FALLBACK_WARNING = "No eligible articles found; fallback report was generated."
LIMITED_COVERAGE_WARNING = (
    "Report has limited source coverage: ranked_articles < 2."
)
ONE_SUMMARY_WARNING = (
    "Only 1 article was summarized; report may not be suitable for external "
    "sharing."
)
MISSING_REPORT_WARNING = "Market analysis report is missing or empty."
WORKFLOW_FAILED_WARNING = "Workflow failed; report is not usable."


def get_now_string() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def generate_run_id(topic: str, run_mode: str) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    safe_topic = sanitize_filename(topic)
    safe_run_mode = sanitize_filename(run_mode)
    return f"{timestamp}_{safe_run_mode}_{safe_topic}"


def create_run_dir(run_id: str) -> Path:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def get_default_outputs() -> dict:
    return {
        name: str(path)
        for name, path in STANDARD_OUTPUTS.items()
    }


def copy_outputs_to_run_dir(run_id: str, outputs=None) -> dict:
    if outputs is None:
        outputs = get_default_outputs()

    run_dir = create_run_dir(run_id)
    copied_outputs = {}

    for name, output_path in outputs.items():
        source_path = Path(output_path)

        if not source_path.exists() or not source_path.is_file():
            continue

        target_path = run_dir / source_path.name
        shutil.copy2(source_path, target_path)
        copied_outputs[name] = str(target_path)

    return copied_outputs


def copy_outputs_to_latest(topic: str, run_id: str) -> dict:
    safe_topic = sanitize_filename(topic)
    latest_dir = LATEST_DIR / safe_topic
    latest_dir.mkdir(parents=True, exist_ok=True)
    run_dir = create_run_dir(run_id)
    copied_outputs = {}

    for source_path in run_dir.iterdir():
        if not source_path.is_file():
            continue

        target_path = latest_dir / source_path.name
        shutil.copy2(source_path, target_path)
        copied_outputs[source_path.name] = str(target_path)

    return copied_outputs


def load_report_index() -> list:
    if not INDEX_FILE.exists():
        return []

    try:
        with INDEX_FILE.open("r", encoding="utf-8") as file:
            index = json.load(file)
    except json.JSONDecodeError:
        print(f"Warning: Report index is not valid JSON: {INDEX_FILE}")
        return []

    if not isinstance(index, list):
        return []

    return index


def save_report_index(index: list) -> None:
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)

    with INDEX_FILE.open("w", encoding="utf-8") as file:
        json.dump(index, file, ensure_ascii=False, indent=2)


def update_report_index(entry: dict) -> None:
    index = load_report_index()
    updated_index = [
        item for item in index
        if item.get("run_id") != entry.get("run_id")
    ]
    updated_index.append(entry)
    updated_index = sorted(
        updated_index,
        key=lambda item: item.get("created_at", ""),
        reverse=True
    )
    save_report_index(updated_index)


def parse_quality_review(path: str) -> dict:
    quality = {
        "quality_score": None,
        "quality_status": None
    }

    if not path:
        return quality

    review_path = Path(path)

    if not review_path.exists() or not review_path.is_file():
        return quality

    text = review_path.read_text(encoding="utf-8")

    for line in text.splitlines():
        if line.startswith("- Total Score:"):
            score_text = line.replace("- Total Score:", "").strip()
            score_text = score_text.split("/")[0].strip()

            try:
                quality["quality_score"] = int(score_text)
            except ValueError:
                quality["quality_score"] = None

        if line.startswith("- Overall Status:"):
            quality["quality_status"] = (
                line.replace("- Overall Status:", "").strip()
            )

    return quality


def path_exists_and_nonempty(path: str) -> bool:
    if not path:
        return False

    output_path = Path(path)
    return (
        output_path.exists()
        and output_path.is_file()
        and output_path.stat().st_size > 0
    )


def get_report_output_path(run_outputs: dict, run_id: str) -> str:
    return run_outputs.get(
        "market_analysis_report",
        get_run_file_path(run_id, "market_analysis_report.md")
    )


def get_quality_warnings(
    workflow_status: str,
    metrics: dict,
    run_outputs: dict,
    run_id: str
) -> list:
    warnings = []
    report_path = get_report_output_path(run_outputs, run_id)

    if workflow_status == "fail":
        warnings.append(WORKFLOW_FAILED_WARNING)

    if not path_exists_and_nonempty(report_path):
        warnings.append(MISSING_REPORT_WARNING)

    if metrics.get("output_type") == "fallback":
        warnings.append(FALLBACK_WARNING)
    elif metrics.get("eligible_articles") == 0:
        warnings.append(FALLBACK_WARNING)

    if metrics and metrics.get("ranked_articles", 0) < 2:
        warnings.append(LIMITED_COVERAGE_WARNING)

    if metrics and metrics.get("successful_summaries", 0) == 1:
        warnings.append(ONE_SUMMARY_WARNING)

    return warnings


def determine_quality_status(
    workflow_status: str,
    metrics: dict,
    run_outputs: dict,
    run_id: str
) -> str:
    report_path = get_report_output_path(run_outputs, run_id)

    if workflow_status == "fail" or not path_exists_and_nonempty(report_path):
        return "fail"

    if (
        workflow_status == "pass"
        and metrics.get("output_type") == "standard"
        and metrics.get("ranked_articles", 0) >= 2
        and metrics.get("successful_summaries", 0) >= 2
    ):
        return "pass"

    return "warning"


def get_quality_recommendation(quality_status: str) -> str:
    if quality_status == "pass":
        return "This report is ready for review."

    if quality_status == "warning":
        return (
            "This report is usable for internal review, but should be reviewed "
            "before sharing due to limited source coverage."
        )

    return "This report is not usable. Please inspect errors and rerun the workflow."


def get_recommended_use(quality_status: str) -> str:
    if quality_status == "pass":
        return "Ready for review."

    if quality_status == "warning":
        return "Internal review only; check source coverage before sharing."

    return "Not usable; inspect errors."


def get_metric_value(metrics: dict, key: str) -> int:
    value = metrics.get(key, 0)

    if isinstance(value, int):
        return value

    return 0


def write_run_text_output(run_id: str, filename: str, content: str) -> str:
    run_dir = create_run_dir(run_id)
    output_path = run_dir / filename
    output_path.write_text(content, encoding="utf-8")
    return str(output_path)


def build_output_quality_review(summary: dict) -> str:
    metrics = summary.get("metrics", {})
    quality_score = summary.get("quality_score")
    warnings = summary.get("warnings", [])
    errors = summary.get("errors", [])
    recommendation = get_quality_recommendation(summary.get("quality_status", "fail"))
    total_score = f"{quality_score}/100" if quality_score is not None else "N/A"

    lines = [
        "# Output Quality Review",
        "",
        f"Run ID: {summary.get('run_id', '')}",
        f"Topic: {summary.get('topic', '')}",
        f"Workflow status: {summary.get('status', '')}",
        f"Quality status: {summary.get('quality_status', '')}",
        f"Output type: {metrics.get('output_type', '')}",
        "",
        "## Summary",
        "",
        f"- Total Score: {total_score}",
        f"- Workflow Status: {summary.get('status', '')}",
        f"- Quality Status: {summary.get('quality_status', '')}",
        f"- Overall Status: {summary.get('quality_status', '')}",
        f"- Output Type: {metrics.get('output_type', '')}",
        f"- Eligible articles: {get_metric_value(metrics, 'eligible_articles')}",
        f"- Ranked articles: {get_metric_value(metrics, 'ranked_articles')}",
        f"- Successful summaries: {get_metric_value(metrics, 'successful_summaries')}",
        "",
        "## Warnings",
        "",
    ]

    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Errors",
        "",
    ])

    if errors:
        for error in errors:
            lines.append(f"- {error}")
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Recommendation",
        "",
        recommendation,
        "",
    ])
    return "\n".join(lines)


def build_review_summary(summary: dict) -> str:
    metrics = summary.get("metrics", {})
    warnings = summary.get("warnings", [])

    lines = [
        "# Weekly Market Intelligence Review",
        "",
        f"Topic: {summary.get('topic', '')}",
        f"Run ID: {summary.get('run_id', '')}",
        f"Workflow status: {summary.get('status', '')}",
        f"Quality status: {summary.get('quality_status', '')}",
        f"Output type: {metrics.get('output_type', '')}",
        "",
        "## Key Metrics",
        "",
        f"- Eligible articles: {get_metric_value(metrics, 'eligible_articles')}",
        f"- Ranked articles: {get_metric_value(metrics, 'ranked_articles')}",
        f"- Successful summaries: {get_metric_value(metrics, 'successful_summaries')}",
        "",
        "## Quality Notes",
        "",
    ]

    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Recommended Use",
        "",
        f"- {get_recommended_use(summary.get('quality_status', 'fail'))}",
        "",
        "## Files",
        "",
        "- market_analysis_report.md",
        "- ranked_sources.md",
        "- output_quality_review.md",
        "- copy_ready_report.md",
        "",
    ])
    return "\n".join(lines)


def read_output_text(run_outputs: dict, key: str) -> str:
    path = run_outputs.get(key, "")

    if not path:
        return ""

    output_path = Path(path)

    if not output_path.exists() or not output_path.is_file():
        return ""

    return output_path.read_text(encoding="utf-8")


def clean_report_excerpt(lines: list, fallback: str) -> str:
    cleaned = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("#"):
            continue

        if stripped.startswith("- ") and any(
            stripped.lower().startswith(prefix)
            for prefix in [
                "- topic:",
                "- template:",
                "- market brief path:",
                "- ranked sources path:",
                "- url:",
            ]
        ):
            continue

        cleaned.append(stripped)

        if len(" ".join(cleaned)) >= 420:
            break

    if not cleaned:
        return fallback

    excerpt = " ".join(cleaned)

    if len(excerpt) > 500:
        return excerpt[:497].rstrip() + "..."

    return excerpt


def extract_report_section(report_text: str, keywords: list) -> str:
    sections = []
    current_section = []

    for line in report_text.splitlines():
        if line.startswith("## "):
            if current_section:
                sections.append(current_section)
            current_section = [line]
        elif current_section:
            current_section.append(line)

    if current_section:
        sections.append(current_section)

    for section in sections:
        heading = section[0].lower()

        if any(keyword.lower() in heading for keyword in keywords):
            return clean_report_excerpt(
                section[1:],
                "No clear section text was extracted from the report."
            )

    return ""


def get_report_fallback_excerpt(report_text: str) -> str:
    return clean_report_excerpt(
        report_text.splitlines(),
        "No report text was available."
    )


def build_copy_ready_report(summary: dict) -> str:
    metrics = summary.get("metrics", {})
    warnings = summary.get("warnings", [])
    report_text = read_output_text(
        summary.get("run_outputs", {}),
        "market_analysis_report"
    )
    fallback_excerpt = get_report_fallback_excerpt(report_text)
    key_trend = (
        extract_report_section(report_text, ["趨勢", "trend", "signal"])
        or fallback_excerpt
    )
    market_pain_point = (
        extract_report_section(report_text, ["痛點", "問題", "pain", "problem"])
        or fallback_excerpt
    )
    product_implication = (
        extract_report_section(report_text, ["產品", "implication"])
        or fallback_excerpt
    )

    lines = [
        f"# {summary.get('topic', '')} Market Intelligence Summary",
        "",
        "## Key Trend",
        "",
        key_trend,
        "",
        "## Market Pain Point",
        "",
        market_pain_point,
        "",
        "## Product Implication",
        "",
        product_implication,
        "",
        "## Source Coverage",
        "",
        f"- Ranked articles: {get_metric_value(metrics, 'ranked_articles')}",
        f"- Successful summaries: {get_metric_value(metrics, 'successful_summaries')}",
        f"- Quality status: {summary.get('quality_status', '')}",
        "",
        "## Notes",
        "",
    ]

    if summary.get("quality_status") == "warning":
        lines.append(
            "This summary is based on limited source coverage and should be "
            "reviewed before sharing."
        )
    elif summary.get("quality_status") == "fail":
        lines.append("This summary is not usable until errors are resolved.")
    elif warnings:
        lines.append("Review warnings before sharing externally.")
    else:
        lines.append("Ready for review.")

    lines.append("")
    return "\n".join(lines)


def write_review_ready_outputs(summary: dict) -> dict:
    run_id = summary["run_id"]
    output_quality_review_path = write_run_text_output(
        run_id,
        "output_quality_review.md",
        build_output_quality_review(summary)
    )
    review_summary_path = write_run_text_output(
        run_id,
        "review_summary.md",
        build_review_summary(summary)
    )
    copy_ready_report_path = write_run_text_output(
        run_id,
        "copy_ready_report.md",
        build_copy_ready_report(summary)
    )

    return {
        "output_quality_review": output_quality_review_path,
        "review_summary": review_summary_path,
        "copy_ready_report": copy_ready_report_path,
    }


def get_run_file_path(run_id: str, filename: str) -> str:
    return str(RUNS_DIR / run_id / filename)


def build_report_index_entry(summary: dict) -> dict:
    run_id = summary.get("run_id", "")
    outputs = summary.get("run_outputs", {})
    quality = parse_quality_review(outputs.get("output_quality_review", ""))
    quality_score = summary.get("quality_score", quality["quality_score"])
    quality_status = summary.get("quality_status", quality["quality_status"])

    return {
        "run_id": run_id,
        "topic": summary.get("topic", ""),
        "run_mode": summary.get("run_mode", ""),
        "created_at": summary.get("created_at", ""),
        "status": summary.get("status", ""),
        "quality_score": quality_score,
        "quality_status": quality_status,
        "report_path": outputs.get(
            "market_analysis_report",
            get_run_file_path(run_id, "market_analysis_report.md")
        ),
        "slide_path": outputs.get(
            "slide_draft",
            get_run_file_path(run_id, "slide_draft.md")
        ),
        "run_summary_path": get_run_file_path(run_id, "run_summary.json"),
        "review_summary_path": outputs.get(
            "review_summary",
            get_run_file_path(run_id, "review_summary.md")
        ),
        "copy_ready_report_path": outputs.get(
            "copy_ready_report",
            get_run_file_path(run_id, "copy_ready_report.md")
        ),
    }


def write_run_summary(run_summary: dict) -> str:
    run_id = run_summary["run_id"]
    run_dir = create_run_dir(run_id)
    summary_path = run_dir / "run_summary.json"

    with summary_path.open("w", encoding="utf-8") as file:
        json.dump(run_summary, file, ensure_ascii=False, indent=2)

    return str(summary_path)


def build_run_summary(
    run_id: str,
    topic: str,
    run_mode: str,
    status: str,
    started_at: str,
    metrics: dict,
    run_outputs: dict,
    cache_paths: dict,
    knowledge_paths: dict,
    quality_status: str,
    quality_score=None,
    warnings=None,
    errors=None
) -> dict:
    if warnings is None:
        warnings = []

    if errors is None:
        errors = []

    finished_at = get_now_string()
    started = datetime.fromisoformat(started_at)
    finished = datetime.fromisoformat(finished_at)

    return {
        "run_id": run_id,
        "topic": topic,
        "run_mode": run_mode,
        "status": status,
        "created_at": started_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round((finished - started).total_seconds(), 2),
        "command": " ".join(sys.argv),
        "quality_status": quality_status,
        "quality_score": quality_score,
        "metrics": metrics,
        "run_outputs": run_outputs,
        "cache_paths": cache_paths,
        "knowledge_paths": knowledge_paths,
        "warnings": warnings,
        "errors": errors
    }


def get_metric_warnings(metrics: dict) -> list:
    warnings = []

    if metrics.get("output_type") == "fallback":
        warnings.append(FALLBACK_WARNING)
    elif metrics.get("eligible_articles") == 0:
        warnings.append(FALLBACK_WARNING)

    return warnings


def merge_warnings(warnings: list, extra_warnings: list) -> list:
    merged = []

    for warning in warnings + extra_warnings:
        if warning not in merged:
            merged.append(warning)

    return merged


def mark_run_success(
    run_id: str,
    topic: str,
    run_mode: str,
    started_at: str,
    metrics: dict,
    outputs: dict,
    cache_paths: dict,
    knowledge_paths: dict,
    warnings=None
) -> dict:
    if warnings is None:
        warnings = []

    warnings = merge_warnings(warnings, get_metric_warnings(metrics))
    run_outputs = copy_outputs_to_run_dir(run_id, outputs)
    quality = parse_quality_review(run_outputs.get("output_quality_review", ""))
    quality_status = determine_quality_status(
        "pass",
        metrics,
        run_outputs,
        run_id
    )
    warnings = merge_warnings(
        warnings,
        get_quality_warnings("pass", metrics, run_outputs, run_id)
    )
    summary = build_run_summary(
        run_id,
        topic,
        run_mode,
        "pass",
        started_at,
        metrics,
        run_outputs,
        cache_paths,
        knowledge_paths,
        quality_status,
        quality["quality_score"],
        warnings
    )
    review_outputs = write_review_ready_outputs(summary)
    summary["run_outputs"].update(review_outputs)
    summary_path = write_run_summary(summary)
    summary["run_summary_path"] = summary_path
    write_run_summary(summary)
    copy_outputs_to_latest(topic, run_id)
    update_report_index(build_report_index_entry(summary))
    return summary


def mark_run_failed(
    run_id: str,
    topic: str,
    run_mode: str,
    started_at: str,
    outputs: dict,
    errors,
    warnings=None
) -> dict:
    if warnings is None:
        warnings = []

    run_outputs = copy_outputs_to_run_dir(run_id, outputs)
    quality_status = determine_quality_status("fail", {}, run_outputs, run_id)
    warnings = merge_warnings(
        warnings,
        get_quality_warnings("fail", {}, run_outputs, run_id)
    )
    summary = build_run_summary(
        run_id,
        topic,
        run_mode,
        "fail",
        started_at,
        {},
        run_outputs,
        {},
        {},
        quality_status,
        None,
        warnings,
        errors
    )
    review_outputs = write_review_ready_outputs(summary)
    summary["run_outputs"].update(review_outputs)
    summary_path = write_run_summary(summary)
    summary["run_summary_path"] = summary_path
    write_run_summary(summary)
    copy_outputs_to_latest(topic, run_id)
    update_report_index(build_report_index_entry(summary))
    return summary
