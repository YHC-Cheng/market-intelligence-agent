from pathlib import Path

from web.models.weekly_report_snapshot import (
    RUNS_DIR,
    build_weekly_report_snapshot_from_run_summary,
)
from web.repositories.json_weekly_report_snapshot_repository import (
    JsonWeeklyReportSnapshotRepository,
)


class RunSummaryNotFoundError(FileNotFoundError):
    pass


class WeeklyReportSnapshotWriter:
    def __init__(self, repository=None, runs_dir=None):
        self.repository = repository or JsonWeeklyReportSnapshotRepository()
        self.runs_dir = Path(runs_dir or RUNS_DIR)

    def write_snapshot_for_run(self, run_id):
        summary_path = self._run_summary_path(run_id)
        if not summary_path.exists() or not summary_path.is_file():
            raise RunSummaryNotFoundError(
                f"run_summary.json not found for run_id: {run_id}"
            )

        snapshot = build_weekly_report_snapshot_from_run_summary(summary_path)
        if not self._is_weekly_snapshot(snapshot):
            raise ValueError(
                f"Run is not a weekly report snapshot: {run_id}"
            )

        return self.repository.save_snapshot(snapshot)

    def backfill_snapshots_from_runs(self):
        result = {
            "scanned_count": 0,
            "created_or_updated_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "errors": [],
        }

        if not self.runs_dir.exists() or not self.runs_dir.is_dir():
            return result

        for run_dir in sorted(self.runs_dir.iterdir()):
            if not run_dir.is_dir():
                continue

            result["scanned_count"] += 1
            summary_path = run_dir / "run_summary.json"

            if not summary_path.exists() or not summary_path.is_file():
                result["skipped_count"] += 1
                continue

            try:
                snapshot = build_weekly_report_snapshot_from_run_summary(
                    summary_path
                )
                if not self._is_weekly_snapshot(snapshot):
                    result["skipped_count"] += 1
                    continue

                self.repository.save_snapshot(snapshot)
                result["created_or_updated_count"] += 1
            except Exception as error:
                result["error_count"] += 1
                result["errors"].append({
                    "run_id": run_dir.name,
                    "run_summary_path": str(summary_path),
                    "error": str(error),
                })

        return result

    def _run_summary_path(self, run_id):
        return self.runs_dir / str(run_id) / "run_summary.json"

    @staticmethod
    def _is_weekly_snapshot(snapshot):
        return snapshot.report_type == "weekly"


def write_snapshot_for_run(run_id, repository=None, runs_dir=None):
    writer = WeeklyReportSnapshotWriter(
        repository=repository,
        runs_dir=runs_dir,
    )
    return writer.write_snapshot_for_run(run_id)


def backfill_snapshots_from_runs(repository=None, runs_dir=None):
    writer = WeeklyReportSnapshotWriter(
        repository=repository,
        runs_dir=runs_dir,
    )
    return writer.backfill_snapshots_from_runs()
