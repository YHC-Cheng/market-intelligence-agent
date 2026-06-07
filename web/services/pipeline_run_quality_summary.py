from copy import deepcopy


MISSING_OUTPUT_STATUSES = {
    "missing",
    "unavailable",
    "not_available",
    "not available",
    "failed",
    "fail",
}


def build_pipeline_run_quality_summary(run):
    run_data = run if isinstance(run, dict) else {}
    warnings = list_value(run_data.get("warnings"))
    errors = list_value(run_data.get("errors"))
    missing_outputs = collect_missing_outputs(run_data.get("run_outputs"))

    summary = {
        "workflow_status": status_value(run_data.get("workflow_status")),
        "quality_status": status_value(run_data.get("quality_status")),
        "quality_score": run_data.get("quality_score"),
        "warning_count": len(warnings),
        "error_count": len(errors),
        "missing_output_count": len(missing_outputs),
        "warnings": warnings,
        "errors": errors,
        "missing_outputs": missing_outputs,
    }
    summary["overall_assessment"] = determine_overall_assessment(summary)
    return summary


def determine_overall_assessment(summary):
    workflow_status = summary.get("workflow_status")
    quality_status = summary.get("quality_status")

    if workflow_status == "fail" or summary.get("error_count", 0) > 0:
        return "Failed"

    if (
        quality_status == "warning"
        or summary.get("warning_count", 0) > 0
        or summary.get("missing_output_count", 0) > 0
    ):
        return "Needs Attention"

    if (
        workflow_status == "pass"
        and quality_status == "pass"
        and summary.get("warning_count", 0) == 0
        and summary.get("error_count", 0) == 0
        and summary.get("missing_output_count", 0) == 0
    ):
        return "Healthy"

    return "Unknown"


def collect_missing_outputs(run_outputs):
    if not isinstance(run_outputs, dict):
        return []

    missing_outputs = []
    for file_key, output in run_outputs.items():
        if not output_is_missing(output):
            continue

        missing_outputs.append({
            "key": file_key,
            "label": file_label(file_key),
            "path": output_path(output),
            "status": output_status(output),
        })

    return missing_outputs


def output_is_missing(output):
    if isinstance(output, dict):
        status = normalized_status(output.get("status"))
        if status in MISSING_OUTPUT_STATUSES:
            return True

        if output.get("available") is False:
            return True

    return False


def output_path(output):
    if isinstance(output, dict):
        value = (
            output.get("path")
            or output.get("file_path")
            or output.get("value")
        )
    else:
        value = output

    if value is None:
        return None

    return str(value)


def output_status(output):
    if isinstance(output, dict):
        status = output.get("status")
        if status:
            return str(status)

        available = output.get("available")
        if isinstance(available, bool):
            return "available" if available else "missing"

    return "unknown"


def normalized_status(value):
    return str(value or "").strip().casefold()


def status_value(value):
    return normalized_status(value) or "unknown"


def list_value(value):
    if isinstance(value, list):
        return deepcopy(value)

    return []


def file_label(file_key):
    return str(file_key).replace("_", " ").title()
