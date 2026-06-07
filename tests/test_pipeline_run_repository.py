import json

from web.repositories.pipeline_run_repository import PipelineRunRepository


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repository(tmp_path):
    outputs_root = tmp_path / "outputs"
    return PipelineRunRepository(outputs_root=outputs_root)


def run_summary(
    run_id,
    created_at="2026-05-16T09:00:00",
    topic="FinOps",
    run_mode="weekly",
    status="pass",
):
    return {
        "run_id": run_id,
        "topic": topic,
        "run_mode": run_mode,
        "status": status,
        "created_at": created_at,
        "finished_at": "2026-05-16T09:02:00",
        "quality_status": "warning",
        "quality_score": 85,
        "warnings": ["Limited coverage."],
        "errors": [],
        "metrics": {
            "output_type": "standard",
            "ranked_articles": 1,
        },
        "run_outputs": {
            "market_analysis_report": (
                f"outputs/runs/{run_id}/market_analysis_report.md"
            ),
            "clean_articles": f"outputs/runs/{run_id}/clean_articles.json",
        },
    }


def write_run_summary(outputs_root, run_id, summary):
    summary_path = outputs_root / "runs" / run_id / "run_summary.json"
    write_json(summary_path, summary)
    return summary_path


def test_list_runs_reads_runs_from_report_index(tmp_path):
    repository = build_repository(tmp_path)
    write_json(
        repository.index_path,
        [
            {
                "run_id": "run-from-index",
                "topic": "AI",
                "run_mode": "weekly",
                "created_at": "2026-05-18T09:00:00",
                "status": "pass",
                "quality_status": "pass",
                "quality_score": 92,
                "report_path": "outputs/runs/run-from-index/report.md",
                "run_summary_path": "outputs/runs/run-from-index/run_summary.json",
            }
        ],
    )

    runs = repository.list_runs()

    assert len(runs) == 1
    assert runs[0]["run_id"] == "run-from-index"
    assert runs[0]["topic"] == "AI"
    assert runs[0]["workflow_status"] == "pass"
    assert runs[0]["quality_status"] == "pass"
    assert runs[0]["quality_score"] == 92
    assert runs[0]["run_outputs"] == {
        "market_analysis_report": "outputs/runs/run-from-index/report.md"
    }


def test_list_runs_falls_back_to_run_summaries_when_index_is_missing(tmp_path):
    repository = build_repository(tmp_path)
    write_run_summary(
        repository.outputs_root,
        "older-run",
        run_summary("older-run", created_at="2026-05-16T09:00:00", topic="AI"),
    )
    write_run_summary(
        repository.outputs_root,
        "newer-run",
        run_summary(
            "newer-run",
            created_at="2026-05-17T09:00:00",
            topic="FinOps",
        ),
    )

    runs = repository.list_runs()

    assert [run["run_id"] for run in runs] == ["newer-run", "older-run"]
    assert runs[0]["topic"] == "FinOps"
    assert runs[0]["workflow_status"] == "pass"
    assert runs[0]["run_summary_path"].endswith(
        "outputs/runs/newer-run/run_summary.json"
    )


def test_get_run_uses_run_summary_as_source_of_truth(tmp_path):
    repository = build_repository(tmp_path)
    write_json(
        repository.index_path,
        [
            {
                "run_id": "same-run",
                "topic": "IndexTopic",
                "run_mode": "weekly",
                "created_at": "2026-05-16T09:00:00",
                "status": "pass",
                "quality_status": "pass",
                "quality_score": 95,
            }
        ],
    )
    write_run_summary(
        repository.outputs_root,
        "same-run",
        run_summary(
            "same-run",
            topic="SummaryTopic",
            run_mode="manual",
            status="fail",
        ),
    )

    run = repository.get_run("same-run")

    assert run["topic"] == "SummaryTopic"
    assert run["run_mode"] == "manual"
    assert run["workflow_status"] == "fail"
    assert run["quality_status"] == "warning"
    assert run["quality_score"] == 85


def test_get_run_outputs_reads_run_outputs_from_run_summary(tmp_path):
    repository = build_repository(tmp_path)
    summary = run_summary("run-with-outputs")
    summary["run_outputs"] = {
        "raw_articles": "outputs/runs/run-with-outputs/articles.json",
        "copy_ready_report": "outputs/runs/run-with-outputs/copy_ready_report.md",
    }
    write_run_summary(repository.outputs_root, "run-with-outputs", summary)

    outputs = repository.get_run_outputs("run-with-outputs")

    assert outputs == {
        "raw_articles": "outputs/runs/run-with-outputs/articles.json",
        "copy_ready_report": "outputs/runs/run-with-outputs/copy_ready_report.md",
    }


def test_missing_fields_use_conservative_fallback_values(tmp_path):
    repository = build_repository(tmp_path)
    write_run_summary(repository.outputs_root, "minimal-run", {"run_id": "minimal-run"})

    run = repository.get_run("minimal-run")

    assert run["run_id"] == "minimal-run"
    assert run["topic"] == "unknown"
    assert run["run_mode"] == "unknown"
    assert run["workflow_status"] == "unknown"
    assert run["quality_status"] == "unknown"
    assert run["quality_score"] is None
    assert run["warnings"] == []
    assert run["errors"] == []
    assert run["metrics"] == {}
    assert run["run_outputs"] == {}


def test_broken_run_summary_does_not_break_list_runs(tmp_path):
    repository = build_repository(tmp_path)
    write_run_summary(
        repository.outputs_root,
        "valid-run",
        run_summary("valid-run"),
    )
    write_text(
        repository.outputs_root / "runs" / "broken-run" / "run_summary.json",
        "{not valid json",
    )

    runs = repository.list_runs()

    assert [run["run_id"] for run in runs] == ["valid-run"]


def test_get_run_returns_none_for_missing_run_id(tmp_path):
    repository = build_repository(tmp_path)

    assert repository.get_run("missing-run") is None


def test_get_run_returns_none_for_broken_run_summary(tmp_path):
    repository = build_repository(tmp_path)
    write_text(
        repository.outputs_root / "runs" / "broken-run" / "run_summary.json",
        "{not valid json",
    )

    assert repository.get_run("broken-run") is None


def test_get_run_outputs_returns_empty_dict_when_run_outputs_are_missing(tmp_path):
    repository = build_repository(tmp_path)
    write_run_summary(
        repository.outputs_root,
        "no-outputs-run",
        {"run_id": "no-outputs-run"},
    )

    assert repository.get_run_outputs("no-outputs-run") == {}


def test_list_runs_sorts_newest_first_from_index(tmp_path):
    repository = build_repository(tmp_path)
    write_json(
        repository.index_path,
        [
            {
                "run_id": "middle-run",
                "generated_at": "2026-05-17T09:00:00",
            },
            {
                "run_id": "older-run",
                "created_at": "2026-05-16T09:00:00",
            },
            {
                "run_id": "newer-run",
                "created_at": "2026-05-18T09:00:00",
            },
        ],
    )

    runs = repository.list_runs()

    assert [run["run_id"] for run in runs] == [
        "newer-run",
        "middle-run",
        "older-run",
    ]
