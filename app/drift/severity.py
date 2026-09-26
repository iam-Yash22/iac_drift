from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple


class Severity(str):
    NONE = "none"
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_DEFAULT_RULES: Dict[str, str] = {
    "tag": Severity.LOW,
    "tags": Severity.LOW,
    "metadata": Severity.MEDIUM,
    "property": Severity.MEDIUM,
    "config": Severity.MEDIUM,
    "ingress": Severity.CRITICAL,
    "egress": Severity.CRITICAL,
    "security_group": Severity.CRITICAL,
    "policy": Severity.CRITICAL,
    "iam": Severity.CRITICAL,
    "bucket_policy": Severity.CRITICAL,
    "route": Severity.HIGH,
    "network": Severity.HIGH,
    "encryption": Severity.HIGH,
    "public_access": Severity.CRITICAL,
    "lifecycle": Severity.HIGH,
    "versioning": Severity.MEDIUM,
    "backup": Severity.MEDIUM,
    "identity": Severity.HIGH,
}


def _normalize_path(path: str) -> str:
    return (path or "").strip().lower().replace(".", " ").replace("[", " ").replace("]", " ")


def _path_tokens(path: str) -> Iterable[str]:
    tokenized = [token for token in _normalize_path(path).split() if token]
    return tokenized


def _matches_rule(path: str, key: str) -> bool:
    normalized = _normalize_path(path)
    return key in normalized or key in {token for token in _path_tokens(path)}


def classify_field_diff(path: str, desired: Any = None, actual: Any = None) -> str:
    """Map a single diff into a severity classification.

    The rule order is intentionally simple and explicit: more sensitive fields
    such as security policy or network access changes are escalated higher than
    tag-only updates.
    """
    if not path:
        return Severity.NONE

    normalized = (path or "").lower()

    if "tag" in normalized or "tags" in normalized:
        return Severity.LOW

    if any(token in normalized for token in ("ingress", "egress", "security_group", "firewall", "acl")):
        return Severity.CRITICAL

    if any(token in normalized for token in ("policy", "iam", "public_access", "bucket_policy", "role")):
        return Severity.CRITICAL

    if any(token in normalized for token in ("network", "subnet", "route", "vpn", "cidr", "gateway")):
        return Severity.HIGH

    if any(token in normalized for token in ("encryption", "backup", "versioning", "lifecycle")):
        return Severity.HIGH

    if any(token in normalized for token in ("metadata", "property", "config")):
        return Severity.MEDIUM

    for rule_name, severity in _DEFAULT_RULES.items():
        if _matches_rule(path, rule_name):
            return severity

    if desired is None or actual is None:
        return Severity.MEDIUM

    if desired != actual:
        return Severity.MEDIUM

    return Severity.NONE


def classify_diff_group(path: str, diff_count: int = 1) -> str:
    if diff_count <= 0:
        return Severity.NONE
    if diff_count == 1:
        return classify_field_diff(path)
    if diff_count <= 3:
        return Severity.MEDIUM
    if diff_count <= 8:
        return Severity.HIGH
    return Severity.CRITICAL


def severity_from_value(value: Any) -> str:
    if value is None:
        return Severity.NONE
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {Severity.NONE, Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL}:
            return lowered
    if isinstance(value, Mapping):
        level = value.get("severity")
        if level is not None:
            return severity_from_value(level)
    return Severity.MEDIUM


def build_rule_table() -> Dict[str, str]:
    return dict(_DEFAULT_RULES)


__all__ = [
    "Severity",
    "build_rule_table",
    "classify_field_diff",
    "classify_diff_group",
    "severity_from_value",
]
