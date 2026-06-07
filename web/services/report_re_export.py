CONTENT_SOURCE_PRIORITY = [
    "copy_ready_report",
    "market_analysis_report",
    "market_brief",
    "review_summary",
]

NO_REPORT_CONTENT_MESSAGE = (
    "No report content file was available for re-export."
)


def build_report_re_export_markdown(snapshot, content_reader=None):
    content_source_key, report_content = select_report_content(
        snapshot,
        content_reader,
    )
    manual_override = normalize_manual_override(snapshot.get("manual_override"))
    title = markdown_value(
        manual_override.get("title")
        if manual_override.get("enabled") and manual_override.get("title")
        else snapshot.get("title") or "Weekly Report"
    )
    lines = [
        f"# {title}",
        "",
        "## Report Metadata",
        "",
        f"- title: {markdown_value(snapshot.get('title'))}",
        f"- topic: {markdown_value(snapshot.get('topic'))}",
        f"- run_id: {markdown_value(snapshot.get('run_id'))}",
        f"- snapshot_id: {markdown_value(snapshot.get('snapshot_id'))}",
        f"- report_type: {markdown_value(snapshot.get('report_type'))}",
        f"- status: {markdown_value(snapshot.get('status'))}",
        f"- quality_status: {markdown_value(snapshot.get('quality_status'))}",
        f"- quality_score: {markdown_value(snapshot.get('quality_score'))}",
        f"- generated_at: {markdown_value(snapshot.get('generated_at'))}",
        f"- created_at: {markdown_value(snapshot.get('created_at'))}",
        "",
        "## Article Counts",
        "",
        f"- article_count: {markdown_value(snapshot.get('article_count', 0))}",
        f"- core_article_count: {markdown_value(snapshot.get('core_article_count', 0))}",
        f"- useful_article_count: {markdown_value(snapshot.get('useful_article_count', 0))}",
        f"- excluded_article_count: {markdown_value(snapshot.get('excluded_article_count', 0))}",
        "",
        "## Quality Warnings",
        "",
    ]

    warnings = snapshot.get("warnings") or []
    if warnings:
        lines.extend([f"- {markdown_value(warning)}" for warning in warnings])
    else:
        lines.append("No warnings")

    if manual_override.get("enabled") and manual_override.get("summary"):
        lines.extend([
            "",
            "## Manual Override Notes",
            "",
            manual_override.get("summary").rstrip(),
        ])

    lines.extend([
        "",
        "## Source Run Metadata",
        "",
    ])

    source_run = snapshot.get("source_run") or {}
    if source_run:
        for key, value in source_run.items():
            lines.append(f"- {key}: {markdown_value(value)}")
    else:
        lines.append("No source run metadata")

    lines.extend([
        "",
        "## Report Content",
        "",
    ])

    if report_content:
        lines.append(f"Source file: {content_source_key}")
        lines.append("")
        lines.append(report_content.rstrip())
    else:
        lines.append(NO_REPORT_CONTENT_MESSAGE)

    lines.extend([
        "",
        "## Output Files",
        "",
    ])

    files = snapshot.get("files") or {}
    if files:
        for file_key, file_metadata in files.items():
            file_metadata = (
                file_metadata if isinstance(file_metadata, dict) else {}
            )
            lines.extend([
                f"### {file_key}",
                "",
                f"- status: {markdown_value(file_metadata.get('status'))}",
                f"- path: {markdown_value(file_metadata.get('path'))}",
                "",
            ])
    else:
        lines.append("No output files recorded")

    return "\n".join(lines).rstrip() + "\n"


def select_report_content(snapshot, content_reader=None):
    if content_reader is None:
        return None, None

    for file_key in CONTENT_SOURCE_PRIORITY:
        try:
            content = content_reader(snapshot, file_key)
        except Exception:
            content = None

        if content:
            return file_key, content

    return None, None


def markdown_value(value):
    if value is None or value == "":
        return "-"

    return str(value)


def normalize_manual_override(manual_override):
    if isinstance(manual_override, dict):
        return {
            "enabled": bool(manual_override.get("enabled")),
            "title": manual_override.get("title"),
            "summary": manual_override.get("summary"),
            "updated_at": manual_override.get("updated_at"),
        }

    return {
        "enabled": bool(manual_override),
        "title": None,
        "summary": None,
        "updated_at": None,
    }
