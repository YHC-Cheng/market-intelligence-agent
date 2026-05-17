import argparse
import json
from pathlib import Path


REPORT_INDEX_FILE = Path("outputs/index/report_index.json")


def load_report_index():
    if not REPORT_INDEX_FILE.exists():
        return []

    try:
        with REPORT_INDEX_FILE.open("r", encoding="utf-8") as file:
            index = json.load(file)
    except json.JSONDecodeError:
        print(f"Warning: Report index is not valid JSON: {REPORT_INDEX_FILE}")
        return []

    if not isinstance(index, list):
        return []

    return sorted(
        index,
        key=lambda item: item.get("created_at", ""),
        reverse=True
    )


def filter_by_topic(entries, topic):
    if not topic:
        return entries

    return [
        entry for entry in entries
        if entry.get("topic") == topic
    ]


def format_entry(entry):
    return "\n".join([
        f"Run ID: {entry.get('run_id', '')}",
        f"Topic: {entry.get('topic', '')}",
        f"Run mode: {entry.get('run_mode', '')}",
        f"Created at: {entry.get('created_at', '')}",
        f"Status: {entry.get('status', '')}",
        f"Quality score: {entry.get('quality_score')}",
        f"Quality status: {entry.get('quality_status')}",
        f"Report: {entry.get('report_path', '')}",
        f"Slide: {entry.get('slide_path', '')}",
        f"Run summary: {entry.get('run_summary_path', '')}",
        f"Review summary: {entry.get('review_summary_path', '')}",
        f"Copy-ready report: {entry.get('copy_ready_report_path', '')}",
    ])


def print_entry_summary(entry):
    print(
        f"{entry.get('created_at', '')} | "
        f"{entry.get('run_id', '')} | "
        f"{entry.get('topic', '')} | "
        f"{entry.get('run_mode', '')} | "
        f"{entry.get('status', '')} | "
        f"quality={entry.get('quality_score')} | "
        f"quality_status={entry.get('quality_status')}"
    )


def handle_latest(args):
    entries = filter_by_topic(load_report_index(), args.topic)

    if not entries:
        print("No reports found.")
        return

    print(format_entry(entries[0]))


def handle_list(args):
    entries = filter_by_topic(load_report_index(), args.topic)
    entries = entries[:args.limit]

    if not entries:
        print("No reports found.")
        return

    for entry in entries:
        print_entry_summary(entry)


def handle_show(args):
    entries = load_report_index()

    for entry in entries:
        if entry.get("run_id") == args.run_id:
            print(format_entry(entry))
            return

    print(f"No report found for run_id: {args.run_id}")


def parse_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    latest_parser = subparsers.add_parser("latest")
    latest_parser.add_argument("--topic", required=True)
    latest_parser.set_defaults(handler=handle_latest)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--topic")
    list_parser.add_argument("--limit", type=int, default=10)
    list_parser.set_defaults(handler=handle_list)

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("--run-id", required=True)
    show_parser.set_defaults(handler=handle_show)

    return parser.parse_args()


def main():
    args = parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
