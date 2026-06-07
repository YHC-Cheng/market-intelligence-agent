import json
from copy import deepcopy
from pathlib import Path

from web.models.weekly_report_snapshot import WeeklyReportSnapshot


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WEEKLY_REPORT_SNAPSHOT_PATH = (
    REPO_ROOT / "data" / "reports" / "weekly_report_snapshots.json"
)


class JsonWeeklyReportSnapshotRepository:
    def __init__(self, snapshot_path=None):
        self.snapshot_path = Path(
            snapshot_path or DEFAULT_WEEKLY_REPORT_SNAPSHOT_PATH
        )

    def list_snapshots(self, topic=None, report_type=None, status=None):
        snapshots = self.load_snapshots()

        if topic is not None:
            snapshots = [
                snapshot for snapshot in snapshots
                if snapshot.get("topic") == topic
            ]

        if report_type is not None:
            snapshots = [
                snapshot for snapshot in snapshots
                if snapshot.get("report_type") == report_type
            ]

        if status is not None:
            snapshots = [
                snapshot for snapshot in snapshots
                if snapshot.get("status") == status
            ]

        return sorted(
            snapshots,
            key=lambda snapshot: (
                snapshot.get("generated_at", ""),
                snapshot.get("created_at", ""),
            ),
            reverse=True,
        )

    def get_snapshot(self, snapshot_id):
        for snapshot in self.load_snapshots():
            if snapshot.get("snapshot_id") == snapshot_id:
                return snapshot

        return None

    def get_by_run_id(self, run_id):
        for snapshot in self.load_snapshots():
            if snapshot.get("run_id") == run_id:
                return snapshot

        return None

    def save_snapshot(self, snapshot):
        snapshot_dict = self._to_dict(snapshot)
        snapshot_id = snapshot_dict.get("snapshot_id")
        run_id = snapshot_dict.get("run_id")
        snapshots = [
            existing
            for existing in self.load_snapshots()
            if (
                existing.get("snapshot_id") != snapshot_id
                and existing.get("run_id") != run_id
            )
        ]
        snapshots.append(deepcopy(snapshot_dict))
        self._write_json(snapshots)
        return deepcopy(snapshot_dict)

    def update_manual_override(self, snapshot_id, manual_override):
        snapshot = self.get_snapshot(snapshot_id)
        if snapshot is None:
            return None

        snapshot["manual_override"] = deepcopy(manual_override)
        return self.save_snapshot(snapshot)

    def load_snapshots(self):
        if not self.snapshot_path.exists():
            return []

        try:
            with self.snapshot_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError:
            return []

        if not isinstance(data, list):
            return []

        return [
            deepcopy(snapshot)
            for snapshot in data
            if isinstance(snapshot, dict)
        ]

    def _write_json(self, snapshots):
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        with self.snapshot_path.open("w", encoding="utf-8") as file:
            json.dump(
                self.list_sorted_snapshots(snapshots),
                file,
                ensure_ascii=False,
                indent=2,
            )

    @staticmethod
    def list_sorted_snapshots(snapshots):
        return sorted(
            snapshots,
            key=lambda snapshot: (
                snapshot.get("generated_at", ""),
                snapshot.get("created_at", ""),
            ),
            reverse=True,
        )

    @staticmethod
    def _to_dict(snapshot):
        if isinstance(snapshot, WeeklyReportSnapshot):
            return snapshot.to_dict()

        return deepcopy(snapshot)
