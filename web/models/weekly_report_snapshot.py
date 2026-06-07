import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO_ROOT / "outputs" / "runs"

WEEKLY_REPORT_OUTPUT_FILES = {
    "run_summary": "run_summary.json",
    "market_brief": "market_brief.md",
    "ranked_sources": "ranked_sources.md",
    "market_analysis_report": "market_analysis_report.md",
    "slide_draft": "slide_draft.md",
    "output_quality_review": "output_quality_review.md",
    "review_summary": "review_summary.md",
    "copy_ready_report": "copy_ready_report.md",
}


@dataclass
class WeeklyReportSnapshot:
    snapshot_id: str
    run_id: str
    topic: str
    report_type: str
    title: str
    created_at: str
    generated_at: str
    status: str
    quality_status: str
    quality_score: Optional[int]
    warnings: list = field(default_factory=list)
    source_run: dict = field(default_factory=dict)
    article_count: int = 0
    core_article_count: int = 0
    useful_article_count: int = 0
    excluded_article_count: int = 0
    files: dict = field(default_factory=dict)
    manual_override: bool = False

    def to_dict(self):
        return asdict(self)


def build_weekly_report_snapshot_from_run_summary(
    run_summary_path,
    snapshot_id=None,
) -> WeeklyReportSnapshot:
    summary_path = Path(run_summary_path)
    with summary_path.open("r", encoding="utf-8") as file:
        summary = json.load(file)

    run_id = str(summary.get("run_id") or summary_path.parent.name)
    topic = str(summary.get("topic") or "")
    files = build_snapshot_files(summary, summary_path, run_id)
    recommendation_counts = count_recommendations_from_ranked_sources(
        files.get("ranked_sources", {}).get("path")
    )
    metrics = summary.get("metrics") or {}

    core_count = first_int_value(
        metrics,
        ["core_article_count", "core_articles", "core_sources"],
        recommendation_counts.get("Core", 0),
    )
    useful_count = first_int_value(
        metrics,
        ["useful_article_count", "useful_articles", "useful_sources"],
        recommendation_counts.get("Useful", 0),
    )
    excluded_count = first_int_value(
        metrics,
        ["excluded_article_count", "excluded_articles", "excluded_sources"],
        recommendation_counts.get("Exclude", 0),
    )
    article_count = first_int_value(
        metrics,
        [
            "article_count",
            "weekly_article_count",
            "ranked_articles",
            "successful_summaries",
            "eligible_articles",
        ],
        core_count + useful_count + excluded_count,
    )

    return WeeklyReportSnapshot(
        snapshot_id=snapshot_id or run_id,
        run_id=run_id,
        topic=topic,
        report_type=str(summary.get("report_type") or "weekly"),
        title=extract_report_title(files) or default_report_title(topic),
        created_at=str(summary.get("created_at") or ""),
        generated_at=str(
            summary.get("generated_at")
            or summary.get("finished_at")
            or summary.get("created_at")
            or ""
        ),
        status=str(summary.get("status") or ""),
        quality_status=str(summary.get("quality_status") or ""),
        quality_score=optional_int(summary.get("quality_score")),
        warnings=summary.get("warnings") if isinstance(summary.get("warnings"), list) else [],
        source_run={
            "run_id": run_id,
            "run_mode": summary.get("run_mode"),
            "run_summary_path": str(summary_path),
        },
        article_count=article_count,
        core_article_count=core_count,
        useful_article_count=useful_count,
        excluded_article_count=excluded_count,
        files=files,
        manual_override=bool(summary.get("manual_override", False)),
    )


def build_snapshot_files(summary, summary_path, run_id):
    run_outputs = summary.get("run_outputs") or {}
    run_dir = summary_path.parent
    files = {}

    for key, filename in WEEKLY_REPORT_OUTPUT_FILES.items():
        path = run_outputs.get(key)
        if key == "run_summary":
            path = summary.get("run_summary_path") or str(summary_path)
        if not path:
            path = str(run_dir / filename) if run_id else None

        files[key] = build_file_record(path)

    return files


def build_file_record(path):
    if not path:
        return {"path": None, "status": "missing"}

    output_path = Path(path)
    if output_path.exists() and output_path.is_file():
        return {"path": str(output_path), "status": "available"}

    return {"path": str(output_path), "status": "missing"}


def extract_report_title(files):
    for key in ["copy_ready_report", "market_analysis_report", "review_summary"]:
        path = files.get(key, {}).get("path")
        if not path or files.get(key, {}).get("status") != "available":
            continue

        title = first_markdown_heading(Path(path))
        if title:
            return title

    return ""


def first_markdown_heading(path):
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
    except OSError:
        return ""

    return ""


def default_report_title(topic):
    if topic:
        return f"{topic} Weekly Report"

    return "Weekly Report"


def count_recommendations_from_ranked_sources(path):
    counts = {"Core": 0, "Useful": 0, "Exclude": 0}
    if not path:
        return counts

    ranked_sources_path = Path(path)
    if not ranked_sources_path.exists() or not ranked_sources_path.is_file():
        return counts

    try:
        lines = ranked_sources_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return counts

    for line in lines:
        recommendation = line.replace("- Recommendation:", "", 1).strip()
        if line.startswith("- Recommendation:") and recommendation in counts:
            counts[recommendation] += 1

    return counts


def first_int_value(data, keys, default=0):
    for key in keys:
        value = optional_int(data.get(key))
        if value is not None:
            return value

    return optional_int(default) or 0


def optional_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None

    return None
