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


def get_run_file_path(run_id: str, filename: str) -> str:
    return str(RUNS_DIR / run_id / filename)


def build_report_index_entry(summary: dict) -> dict:
    run_id = summary.get("run_id", "")
    outputs = summary.get("run_outputs", {})
    quality = parse_quality_review(outputs.get("output_quality_review", ""))

    return {
        "run_id": run_id,
        "topic": summary.get("topic", ""),
        "run_mode": summary.get("run_mode", ""),
        "created_at": summary.get("created_at", ""),
        "status": summary.get("status", ""),
        "quality_score": quality["quality_score"],
        "quality_status": quality["quality_status"],
        "report_path": outputs.get(
            "market_analysis_report",
            get_run_file_path(run_id, "market_analysis_report.md")
        ),
        "slide_path": outputs.get(
            "slide_draft",
            get_run_file_path(run_id, "slide_draft.md")
        ),
        "run_summary_path": get_run_file_path(run_id, "run_summary.json")
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
        warnings.append("No eligible articles found; fallback report was generated.")
    elif metrics.get("eligible_articles") == 0:
        warnings.append("No eligible articles found; fallback report was generated.")

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
        warnings
    )
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
        warnings,
        errors
    )
    summary_path = write_run_summary(summary)
    summary["run_summary_path"] = summary_path
    write_run_summary(summary)
    copy_outputs_to_latest(topic, run_id)
    update_report_index(build_report_index_entry(summary))
    return summary
