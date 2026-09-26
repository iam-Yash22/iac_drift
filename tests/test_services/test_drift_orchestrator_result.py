from app.drift.engine import DriftResult
from app.services.drift_orchestrator import _scan_result


def test_scan_result_serializes_drift_result_to_fixed_schema():
    result = _scan_result(
        DriftResult(
            resource_id="resource-1",
            resource_type="aws_instance",
            is_drifted=True,
            severity="high",
            diffs={"size": {"desired": "small", "actual": "large"}},
            summary="Detected drift.",
        ),
        total_resources=3,
    )

    assert result["summary"] == {
        "total_resources": 3,
        "drifted_resources": 1,
        "severity_breakdown": {"high": 1},
    }
    assert result["drifts"][0]["resource_id"] == "resource-1"
    assert result["drifts"][0]["diffs"]["size"]["actual"] == "large"
    assert result["scanned_at"]