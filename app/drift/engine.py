from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from app.core.logging_config import get_logger
from app.core.config import KNOWN_AWS_DEFAULTS

try:  # pragma: no cover - optional project-level dependency
    from app.drift.comparators import compare_values as _compare_values
    from app.drift.comparators import ignored_fields as _ignored_fields
except Exception:  # pragma: no cover
    _compare_values = None
    _ignored_fields = lambda resource_type: set()

try:  # pragma: no cover - optional project-level dependency
    from app.drift.severity import Severity
except Exception:  # pragma: no cover
    class Severity(str):
        NONE = "none"
        INFO = "info"
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"


logger = get_logger(__name__)


@dataclass(frozen=True)
class NormalizedResource:
    """Normalized representation of a tracked resource.

    The model is intentionally permissive so the pure compare function can work
    against a variety of resource shapes without introducing I/O or framework
    dependencies.
    """

    resource_id: str = ""
    resource_type: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DriftResult:
    resource_id: str = ""
    resource_type: str = ""
    is_drifted: bool = False
    severity: str = Severity.NONE
    diffs: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    is_known_exception: bool = False

    @property
    def drifted(self) -> bool:
        return self.is_drifted

    @property
    def changes(self) -> Dict[str, Any]:
        return self.diffs

    @property
    def differences(self) -> Dict[str, Any]:
        return self.diffs


def _normalize_value(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _normalize_value(v) for k, v in value.items()}
    if isinstance(value, set):
        return sorted(_normalize_value(item) for item in value)
    return value


def _flatten_mapping(prefix: str, payload: Mapping[str, Any]) -> Iterable[Tuple[str, Any]]:
    for key, value in sorted(payload.items(), key=lambda item: str(item[0])):
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            yield from _flatten_mapping(path, value)
        else:
            yield path, value


def _compare_scalar(desired: Any, actual: Any, resource_type: str = "") -> bool:
    if _compare_values is not None:
        try:
            return bool(_compare_values(desired, actual, resource_type))
        except Exception:
            pass
    return desired == actual


def _collect_differences(
    desired: Any,
    actual: Any,
    path: str = "",
    resource_type: str = "",
) -> List[Tuple[str, Any, Any]]:
    if desired is None and actual is None:
        return []

    if isinstance(desired, Mapping) and isinstance(actual, Mapping):
        differences: List[Tuple[str, Any, Any]] = []
        all_keys = sorted(set(desired.keys()) | set(actual.keys()), key=str)
        for key in all_keys:
            if str(key).lower() in _ignored_fields(resource_type):
                continue
            child_path = f"{path}.{key}" if path else str(key)
            if key not in desired:
                differences.append((child_path, None, actual[key]))
            elif key not in actual:
                differences.append((child_path, desired[key], None))
            else:
                differences.extend(
                    _collect_differences(desired[key], actual[key], child_path, resource_type)
                )
        return differences

    if isinstance(desired, (list, tuple)) and isinstance(actual, (list, tuple)):
        if len(desired) != len(actual):
            return [(path, _normalize_value(desired), _normalize_value(actual))]
        differences: List[Tuple[str, Any, Any]] = []
        for idx, (left, right) in enumerate(zip(desired, actual)):
            item_path = f"{path}[{idx}]" if path else f"[{idx}]"
            differences.extend(_collect_differences(left, right, item_path, resource_type))
        return differences

    if isinstance(desired, set) and isinstance(actual, set):
        if desired != actual:
            return [(path, _normalize_value(sorted(desired)), _normalize_value(sorted(actual)))]
        return []

    if not _compare_scalar(desired, actual, resource_type):
        return [(path, _normalize_value(desired), _normalize_value(actual))]

    return []


def _compute_severity(diffs: Sequence[Tuple[str, Any, Any]]) -> str:
    if not diffs:
        return Severity.NONE
    total = len(diffs)
    if total <= 1:
        return Severity.LOW
    if total <= 3:
        return Severity.MEDIUM
    if total <= 8:
        return Severity.HIGH
    return Severity.CRITICAL


def _is_known_aws_default(resource: Any, resource_type: str) -> bool:
    attributes = (
        getattr(resource, "attributes", {})
        or getattr(resource, "properties", {})
        or {}
    )
    for rule in KNOWN_AWS_DEFAULTS:
        if rule.get("resource_type") != resource_type:
            continue
        value = attributes.get(rule.get("attribute", ""))
        pattern = rule.get("pattern", "")
        if rule.get("operator") == "equals" and value == pattern:
            return True
        if rule.get("operator") == "starts_with" and isinstance(value, str) and value.startswith(pattern):
            return True
    return False


def compare(desired: NormalizedResource, actual: NormalizedResource) -> DriftResult:
    """Compare a desired normalized resource against the live resource state.

    The function is intentionally pure: it relies on in-memory values only and
    never performs any I/O, network calls, or persistence operations.
    """

    if desired is None and actual is None:
        return DriftResult(
            resource_id="",
            resource_type="",
            is_drifted=False,
            severity=Severity.NONE,
            diffs={},
            summary="No drift detected.",
        )

    if desired is None or actual is None:
        diff_payload = {
            "resource": {
                "desired": None,
                "actual": actual if desired is None else desired,
            }
        }
        return DriftResult(
            resource_id=(getattr(actual, "resource_id", "") if desired is None else getattr(desired, "resource_id", "")),
            resource_type=(getattr(actual, "resource_type", "") if desired is None else getattr(desired, "resource_type", "")),
            is_drifted=True,
            severity=Severity.CRITICAL,
            diffs=diff_payload,
            summary="Resource exists in only one state.",
        )

    desired_payload = {
        "properties": getattr(desired, "properties", None)
        or getattr(desired, "attributes", {})
        or {},
        "tags": getattr(desired, "tags", {}) or {},
        "metadata": getattr(desired, "metadata", {}) or {},
    }
    actual_payload = {
        "properties": getattr(actual, "properties", None)
        or getattr(actual, "attributes", {})
        or {},
        "tags": getattr(actual, "tags", {}) or {},
        "metadata": getattr(actual, "metadata", {}) or {},
    }
    resource_type = str(getattr(desired, "resource_type", "") or getattr(actual, "resource_type", ""))

    differences: List[Tuple[str, Any, Any]] = []
    for section in ("properties", "tags", "metadata"):
        differences.extend(
            _collect_differences(
                desired_payload[section],
                actual_payload[section],
                section,
                resource_type,
            )
        )

    diff_map: Dict[str, Any] = {}
    for field_path, desired_value, actual_value in differences:
        diff_map[field_path] = {"desired": _normalize_value(desired_value), "actual": _normalize_value(actual_value)}

    drifted = bool(diff_map)
    severity = _compute_severity(differences)
    summary = (
        "No drift detected."
        if not drifted
        else f"Detected {len(diff_map)} drifted field(s) with {severity} severity."
    )

    return DriftResult(
        resource_id=(
            getattr(desired, "resource_id", "")
            or getattr(desired, "id", "")
            or getattr(actual, "resource_id", "")
            or getattr(actual, "id", "")
        ),
        resource_type=(
            getattr(desired, "resource_type", "")
            or getattr(desired, "type", "")
            or getattr(actual, "resource_type", "")
            or getattr(actual, "type", "")
        ),
        is_drifted=drifted,
        severity=severity,
        diffs=diff_map,
        summary=summary,
    )


def compare_resources(
    desired_resources: Iterable[Any],
    actual_resources: Iterable[Any],
) -> List[DriftResult]:
    """Compare every live resource with its matching desired resource."""
    desired = list(desired_resources or [])
    results: List[DriftResult] = []

    type_map = {
        "aws_s3_bucket": "s3_bucket",
        "aws_iam_role": "iam_role",
        "aws_security_group": "security_group",
        "aws_lambda_function": "lambda_function",
        "aws_elastic_beanstalk_environment": "elastic_beanstalk_environment",
    }

    for actual in actual_resources or []:
        actual_id = getattr(actual, "resource_id", None) or getattr(actual, "id", None)
        actual_type = getattr(actual, "resource_type", None) or getattr(actual, "type", None)
        actual_name = getattr(actual, "resource_name", None) or getattr(actual, "name", None)

        match = next(
            (
                item
                for item in desired
                if (
                    actual_id
                    and (getattr(item, "resource_id", None) or getattr(item, "id", None)) == actual_id
                )
                or (
                    actual_type
                    and actual_name
                    and type_map.get(
                        getattr(item, "resource_type", None) or getattr(item, "type", None),
                        getattr(item, "resource_type", None) or getattr(item, "type", None),
                    ) == actual_type
                    and (getattr(item, "resource_name", None) or getattr(item, "name", None)) == actual_name
                )
            ),
            None,
        )

        if match is None:
            logger.info(
                "tags resource_id=%s desired=%s actual=%s",
                actual_id,
                {},
                getattr(actual, "tags", {}) or {},
            )
            known_exception = _is_known_aws_default(actual, str(actual_type or ""))
            unmatched_result = DriftResult(
                resource_id=str(actual_id or ""),
                resource_type=str(actual_type or ""),
                is_drifted=True,
                severity=Severity.INFO if known_exception else Severity.CRITICAL,
                diffs={"resource": {"desired": None, "actual": getattr(actual, "to_dict", lambda: actual)()}},
                summary=(
                    "Known AWS default resource has no matching desired baseline."
                    if known_exception
                    else "Resource has no matching desired baseline."
                ),
                is_known_exception=known_exception,
            )
            logger.info(
                "comparison resource_id=%s is_drifted=%s diffs=%s",
                actual_id,
                unmatched_result.is_drifted,
                unmatched_result.diffs,
            )
            results.append(
                unmatched_result
            )
            continue

        desired_arn = getattr(match, "arn", None)
        actual_arn = getattr(actual, "arn", None)
        desired_attributes = getattr(match, "attributes", {}) or {}
        actual_attributes = getattr(actual, "attributes", {}) or {}
        shared_attributes = {
            key: desired_attributes[key]
            for key in desired_attributes.keys() & actual_attributes.keys()
        }
        actual_shared_attributes = {key: actual_attributes[key] for key in shared_attributes}
        desired_identity = NormalizedResource(
            resource_id=str(getattr(match, "resource_id", "") or ""),
            resource_type=str(getattr(match, "resource_type", "") or ""),
            properties={
                "resource_id": str(getattr(match, "resource_id", "") or ""),
                "resource_type": str(getattr(match, "resource_type", "") or ""),
                "resource_name": str(getattr(match, "resource_name", "") or ""),
                "arn": str(desired_arn or ""),
                **shared_attributes,
            },
            tags=getattr(match, "tags", {}) or {},
        )
        actual_identity = NormalizedResource(
            resource_id=str(actual_id or ""),
            resource_type=str(actual_type or ""),
            properties={
                "resource_id": str(actual_id or ""),
                "resource_type": str(actual_type or ""),
                "resource_name": str(actual_name or ""),
                "arn": str(actual_arn or ""),
                **actual_shared_attributes,
            },
            tags=getattr(actual, "tags", {}) or {},
        )
        logger.info(
            "tags resource_id=%s desired=%s actual=%s",
            actual_id,
            desired_identity.tags,
            actual_identity.tags,
        )
        if str(actual_id) == "arn:aws:s3:::b1-740122274365" or str(actual_name) == "b1-740122274365":
            print(f"[DEBUG S3 MATCH] desired_identity={desired_identity}")
            print(f"[DEBUG S3 MATCH] actual_identity={actual_identity}")

        try:
            result = compare(desired_identity, actual_identity)
        except Exception:
            logger.error("comparison failed resource_id=%s", actual_id, exc_info=True)
            raise
        logger.info(
            "comparison resource_id=%s is_drifted=%s diffs=%s",
            actual_id,
            result.is_drifted,
            result.diffs,
        )
        if str(actual_id) == "arn:aws:s3:::b1-740122274365" or str(actual_name) == "b1-740122274365":
            print(f"[DEBUG S3 MATCH RESULT] compare_result={result}")

        results.append(
            DriftResult(
                resource_id=str(result.resource_id or actual_id or ""),
                resource_type=str(result.resource_type or actual_type or ""),
                is_drifted=result.is_drifted,
                severity=result.severity,
                diffs=result.diffs,
                summary=result.summary,
                is_known_exception=result.is_known_exception,
            )
        )

    return results


__all__ = ["NormalizedResource", "DriftResult", "compare", "compare_resources"]
