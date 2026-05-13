import sys
from datetime import datetime
from pathlib import Path

import feedparser

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from config import RSS_SOURCES_BY_TOPIC


REPORT_FILE = REPO_ROOT / "outputs/reports/source_validation_report.md"
TOP_ENTRIES_LIMIT = 3


def validate_source(topic, source):
    result = {
        "topic": topic,
        "name": source.get("name", ""),
        "category": source.get("category", ""),
        "url": source.get("url", ""),
        "status": "failed",
        "entries_count": 0,
        "top_entries": [],
        "error": ""
    }

    try:
        feed = feedparser.parse(result["url"])
        entries = feed.entries
        result["entries_count"] = len(entries)
        result["top_entries"] = [
            entry.get("title", "Untitled")
            for entry in entries[:TOP_ENTRIES_LIMIT]
        ]

        if entries:
            result["status"] = "success"
        else:
            result["status"] = "failed"

        if feed.get("bozo_exception"):
            result["error"] = str(feed.bozo_exception)
    except Exception as error:
        result["status"] = "failed"
        result["error"] = str(error)

    return result


def validate_sources():
    results = []

    for topic, sources in RSS_SOURCES_BY_TOPIC.items():
        for source in sources:
            result = validate_source(topic, source)
            results.append(result)
            print(
                f"[{topic}] {result['name']} - {result['status']} - "
                f"{result['entries_count']} entries"
            )

    return results


def create_markdown_report(results):
    total_sources = len(results)
    success_count = sum(1 for result in results if result["status"] == "success")
    failed_count = total_sources - success_count
    generated_at = datetime.now().replace(microsecond=0).isoformat()

    lines = [
        "# Source Validation Report",
        "",
        f"Generated at: {generated_at}",
        "",
        "## Summary",
        "",
        f"- Total sources: {total_sources}",
        f"- Success: {success_count}",
        f"- Failed: {failed_count}",
        "",
        "## Results by Topic",
        ""
    ]

    for topic, sources in RSS_SOURCES_BY_TOPIC.items():
        lines.extend([
            f"### {topic}",
            ""
        ])

        topic_results = [
            result for result in results
            if result["topic"] == topic
        ]

        for result in topic_results:
            lines.extend([
                f"#### {result['name']}",
                "",
                f"- Status: {result['status']}",
                f"- Category: {result['category']}",
                f"- URL: {result['url']}",
                f"- Entries count: {result['entries_count']}"
            ])

            if result["error"]:
                lines.append(f"- Error: {result['error']}")

            lines.extend([
                "",
                "Top entries:"
            ])

            if result["top_entries"]:
                for index, title in enumerate(result["top_entries"], start=1):
                    lines.append(f"{index}. {title}")
            else:
                lines.append("No entries available.")

            lines.append("")

    return "\n".join(lines)


def save_report(content):
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with REPORT_FILE.open("w", encoding="utf-8") as file:
        file.write(content)


def main():
    print("Validating sources...")
    print("")

    results = validate_sources()
    report = create_markdown_report(results)
    save_report(report)

    print("")
    print("Validation completed.")
    print(f"Saved report to {REPORT_FILE.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
