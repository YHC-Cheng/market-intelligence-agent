import json
from copy import deepcopy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUTS_ROOT = REPO_ROOT / "outputs"

DEFAULT_RUN_VALUES = {
    "topic": "unknown",
    "run_mode": "unknown",
    "workflow_status": "unknown",
    "quality_status": "unknown",
    "quality_score": None,
    "warnings": [],
    "errors": [],
    "metrics": {},
    "run_outputs": {},
}


class PipelineRunRepository:
    def __init__(self, outputs_root=None, index_path=None, runs_dir=None):
        self.outputs_root = Path(outputs_root or DEFAULT_OUTPUTS_ROOT)
        self.index_path = Path(
            index_path or self.outputs_root / "index" / "report_index.json"
        )
        self.runs_dir = Path(runs_dir or self.outputs_root / "runs")

    def list_runs(self):
        index_runs = self._load_runs_from_index()
        if index_runs:
            return self._sort_runs(index_runs)

        return self._sort_runs(self._load_runs_from_run_summaries())

    def get_run(self, run_id):
        summary_path = self._run_summary_path(run_id)
        summary = self._read_json_object(summary_path)

        if summary is None:
            return None

        return self._normalize_run(summary, summary_path=summary_path)

    def get_run_outputs(self, run_id):
        run = self.get_run(run_id)
        if run is None:
            return {}

        return deepcopy(run.get("run_outputs") or {})

    def _load_runs_from_index(self):
        index = self._read_json_array(self.index_path)
        if index is None:
            return []

        runs = []
        for entry in index:
            if not isinstance(entry, dict):
                continue

            run_id = entry.get("run_id")
            if not run_id:
                continue

            summary_path = self._summary_path_from_index_entry(entry, run_id)
            runs.append(self._normalize_run(entry, summary_path=summary_path))

        return runs

    def _load_runs_from_run_summaries(self):
        if not self.runs_dir.exists() or not self.runs_dir.is_dir():
            return []

        runs = []
        for run_dir in sorted(self.runs_dir.iterdir()):
            if not run_dir.is_dir():
                continue

            summary_path = run_dir / "run_summary.json"
            summary = self._read_json_object(summary_path)
            if summary is None:
                continue

            runs.append(self._normalize_run(summary, summary_path=summary_path))

        return runs

    def _normalize_run(self, raw_run, summary_path=None):
        run = deepcopy(raw_run) if isinstance(raw_run, dict) else {}
        run_id = str(run.get("run_id") or self._run_id_from_path(summary_path))
        workflow_status = run.get("workflow_status", run.get("status"))
        created_at = run.get("created_at") or run.get("generated_at") or ""
        generated_at = run.get("generated_at") or run.get("finished_at") or created_at

        normalized = {
            "run_id": run_id,
            "topic": run.get("topic") or DEFAULT_RUN_VALUES["topic"],
            "run_mode": run.get("run_mode") or DEFAULT_RUN_VALUES["run_mode"],
            "created_at": str(created_at or ""),
            "generated_at": str(generated_at or ""),
            "workflow_status": (
                workflow_status or DEFAULT_RUN_VALUES["workflow_status"]
            ),
            "quality_status": (
                run.get("quality_status")
                or DEFAULT_RUN_VALUES["quality_status"]
            ),
            "quality_score": run.get("quality_score"),
            "warnings": self._list_or_default(
                run.get("warnings"),
                DEFAULT_RUN_VALUES["warnings"],
            ),
            "errors": self._list_or_default(
                run.get("errors"),
                DEFAULT_RUN_VALUES["errors"],
            ),
            "metrics": self._dict_or_default(
                run.get("metrics"),
                DEFAULT_RUN_VALUES["metrics"],
            ),
            "run_outputs": self._normalize_run_outputs(run),
            "run_summary_path": str(
                summary_path or self._run_summary_path(run_id)
            ),
        }

        if normalized["quality_score"] is not None:
            normalized["quality_score"] = self._optional_int(
                normalized["quality_score"]
            )

        return normalized

    def _normalize_run_outputs(self, run):
        run_outputs = self._dict_or_default(
            run.get("run_outputs"),
            DEFAULT_RUN_VALUES["run_outputs"],
        )
        if run_outputs:
            return run_outputs

        output_paths = {
            "market_analysis_report": run.get("report_path"),
            "slide_draft": run.get("slide_path"),
            "review_summary": run.get("review_summary_path"),
            "copy_ready_report": run.get("copy_ready_report_path"),
        }
        return {
            key: value
            for key, value in output_paths.items()
            if value
        }

    def _summary_path_from_index_entry(self, entry, run_id):
        path = entry.get("run_summary_path")
        if path:
            return self._path_from_output_value(path)

        return self._run_summary_path(run_id)

    def _path_from_output_value(self, value):
        path = Path(value)
        if path.is_absolute():
            return path

        return REPO_ROOT / path

    def _run_summary_path(self, run_id):
        return self.runs_dir / str(run_id) / "run_summary.json"

    @staticmethod
    def _run_id_from_path(summary_path):
        if summary_path is None:
            return ""

        return Path(summary_path).parent.name

    @staticmethod
    def _read_json_object(path):
        try:
            with Path(path).open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict):
            return None

        return data

    @staticmethod
    def _read_json_array(path):
        try:
            with Path(path).open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, list):
            return None

        return data

    @staticmethod
    def _list_or_default(value, default):
        if isinstance(value, list):
            return deepcopy(value)

        return deepcopy(default)

    @staticmethod
    def _dict_or_default(value, default):
        if isinstance(value, dict):
            return deepcopy(value)

        return deepcopy(default)

    @staticmethod
    def _optional_int(value):
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

    @staticmethod
    def _sort_runs(runs):
        return sorted(
            runs,
            key=lambda run: (
                run.get("created_at", ""),
                run.get("generated_at", ""),
                run.get("run_id", ""),
            ),
            reverse=True,
        )
