from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

import app.dashboard.aggregators as aggregators


__all__ = [
    "build_7_day_trend",
    "build_top_resource_widget",
    "build_top_offending_resources",
    "build_widgets",
]


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "dict"):
        try:
            value = value.dict()
            if isinstance(value, Mapping):
                return value
        except Exception:
            pass
    return {}


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_day_items(items: Optional[Iterable[Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in items or []:
        mapping = _as_mapping(item)
        if not mapping:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                day, count = item[0], item[1]
                normalized.append({"date": str(day), "count": _coerce_int(count)})
            continue
        day = mapping.get("date") or mapping.get("day") or mapping.get("created_at") or mapping.get("detected_day")
        count = mapping.get("count", mapping.get("value", 0))
        if day is not None:
            normalized.append({"date": str(day), "count": _coerce_int(count)})
    return normalized


def _build_last_7_day_labels() -> List[str]:
    today = datetime.now(timezone.utc).date()
    return [(today - timedelta(days=offset)).isoformat() for offset in range(6, -1, -1)]


def _merge_day_counts(summary: Mapping[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    day_values = summary.get("by_day") or summary.get("daily_counts") or []
    for entry in _normalize_day_items(day_values):
        counts[str(entry.get("date", ""))] = _coerce_int(entry.get("count"), 0)
    return counts


def build_7_day_trend(summary: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Return a 7-day trend widget from dashboard summary data."""
    payload = _as_mapping(summary) if summary is not None else {}
    if not payload and hasattr(aggregators, "aggregate"):
        try:
            payload = _as_mapping(aggregators.aggregate())
        except Exception:
            payload = {}

    labels = _build_last_7_day_labels()
    counts = _merge_day_counts(payload)
    series = [counts.get(label, 0) for label in labels]

    return {
        "type": "line",
        "title": "7-day drift trend",
        "labels": labels,
        "series": series,
        "data": [{"date": label, "count": count} for label, count in zip(labels, series)],
    }


def build_top_offending_resources(summary: Optional[Mapping[str, Any]] = None, limit: int = 5) -> Dict[str, Any]:
    """Return the top offending resources from a summary payload."""
    payload = _as_mapping(summary) if summary is not None else {}
    if not payload:
        payload = _as_mapping(getattr(aggregators, "aggregate", lambda: {})()) if hasattr(aggregators, "aggregate") else {}

    candidates = payload.get("top_offending_resources")
    if candidates is None:
        candidates = payload.get("offending_resources")
    if candidates is None:
        candidates = payload.get("resources")
    if candidates is None:
        candidates = []

    normalized: List[Dict[str, Any]] = []
    for item in candidates or []:
        mapping = _as_mapping(item)
        if not mapping:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                resource_id, count = item[0], item[1]
                normalized.append({"resource_id": resource_id, "count": _coerce_int(count)})
            continue
        resource_id = mapping.get("resource_id") or mapping.get("resource") or mapping.get("name") or mapping.get("id")
        count = mapping.get("count", mapping.get("drift_count", 0))
        if resource_id is not None:
            normalized.append({"resource_id": resource_id, "count": _coerce_int(count)})

    normalized.sort(key=lambda x: x.get("count", 0), reverse=True)
    limited = normalized[: max(0, int(limit))]

    return {
        "type": "bar",
        "title": "Top offending resources",
        "items": limited,
        "limit": max(0, int(limit)),
    }


def build_top_resource_widget(summary: Optional[Mapping[str, Any]] = None, limit: int = 5) -> Dict[str, Any]:
    return build_top_offending_resources(summary=summary, limit=limit)


def build_widgets(summary: Optional[Mapping[str, Any]] = None, limit: int = 5) -> Dict[str, Any]:
    """Build all dashboard widgets in a single payload."""
    payload = _as_mapping(summary) if summary is not None else {}
    if not payload and hasattr(aggregators, "aggregate"):
        try:
            payload = _as_mapping(aggregators.aggregate())
        except Exception:
            payload = {}

    return {
        "seven_day_trend": build_7_day_trend(payload),
        "top_offending_resources": build_top_offending_resources(payload, limit=limit),
    }
