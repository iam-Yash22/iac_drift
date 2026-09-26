from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

import app.crud.crud_drift as crud_drift
import app.crud.crud_resource as crud_resource


__all__ = ["aggregate", "aggregate_summary", "get_summary", "summarize"]


def _coerce_count(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _coerce_since(filters: Optional[Mapping[str, Any]]) -> Optional[Any]:
    if not filters:
        return None
    for key in ("since", "start_date", "date_from", "from_date"):
        value = filters.get(key)
        if value is not None:
            return value
    return None


def _coerce_day(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.date().isoformat()
        except Exception:
            pass
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10]


def _lookup_raw_rows(filters: Mapping[str, Any], names: Iterable[str]) -> List[Any]:
    for name in names:
        value = filters.get(name)
        if value is not None:
            return value if isinstance(value, list) else [value]
    return []


def _normalize_severity_rows(rows: Iterable[Any]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for row in rows or []:
        if isinstance(row, Mapping):
            key = row.get("severity")
            if key is None:
                key = row.get("name")
            count = row.get("count", row.get("value", 0))
            if key is not None:
                result[str(key).lower()] = _coerce_count(count)
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            key, count = row[0], row[1]
            result[str(key).lower()] = _coerce_count(count)
    return result


def _normalize_account_rows(rows: Iterable[Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for row in rows or []:
        if isinstance(row, Mapping):
            account_id = row.get("account_id")
            if account_id is None:
                account_id = row.get("account")
            count = row.get("count", row.get("value", 0))
            if account_id is not None:
                result.append({"account_id": account_id, "count": _coerce_count(count)})
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            account_id, count = row[0], row[1]
            result.append({"account_id": account_id, "count": _coerce_count(count)})
    return result


def _normalize_day_rows(rows: Iterable[Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for row in rows or []:
        if isinstance(row, Mapping):
            day = row.get("day") or row.get("date") or row.get("created_at") or row.get("detected_day")
            count = row.get("count", row.get("value", 0))
            normalized_day = _coerce_day(day)
            if normalized_day is not None:
                result.append({"date": normalized_day, "count": _coerce_count(count)})
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            day, count = row[0], row[1]
            normalized_day = _coerce_day(day)
            if normalized_day is not None:
                result.append({"date": normalized_day, "count": _coerce_count(count)})
    return result


def _lookup_crud_rows(filters: Mapping[str, Any], db: Any = None) -> Dict[str, List[Any]]:
    if db is None:
        return {
            "severity": _lookup_raw_rows(filters, ("severity_counts", "by_severity", "drift_counts_by_severity", "severity")),
            "account": _lookup_raw_rows(filters, ("account_counts", "by_account", "drift_counts_by_account", "account")),
            "day": _lookup_raw_rows(filters, ("daily_counts", "by_day", "day_counts", "drift_counts_by_day", "days")),
        }

    rows: Dict[str, List[Any]] = {"severity": [], "account": [], "day": []}
    since = _coerce_since(filters)

    severity_fn = getattr(crud_drift, "count_by_severity", None)
    if callable(severity_fn):
        try:
            rows["severity"] = severity_fn(db, since=since)
        except TypeError:
            rows["severity"] = severity_fn(db)

    account_fn = getattr(crud_drift, "count_by_account", None)
    if callable(account_fn):
        try:
            rows["account"] = account_fn(db, since=since)
        except TypeError:
            rows["account"] = account_fn(db)

    day_fn = getattr(crud_drift, "count_by_day", None)
    if callable(day_fn):
        try:
            rows["day"] = day_fn(db, since=since)
        except TypeError:
            rows["day"] = day_fn(db)

    if not rows["day"]:
        day_like = getattr(crud_drift, "count_by_date", None)
        if callable(day_like):
            try:
                rows["day"] = day_like(db, since=since)
            except TypeError:
                rows["day"] = day_like(db)

    return rows


def aggregate(filters: Optional[Mapping[str, Any]] = None, db: Any = None) -> Dict[str, Any]:
    """Return a JSON-serializable dashboard summary from raw drift aggregation rows."""
    filters = dict(filters or {})
    raw_rows = _lookup_crud_rows(filters, db=db)

    severity_counts = _normalize_severity_rows(raw_rows.get("severity") or [])
    account_counts = _normalize_account_rows(raw_rows.get("account") or [])
    day_counts = _normalize_day_rows(raw_rows.get("day") or [])

    if not severity_counts:
        severity_counts = _normalize_severity_rows(
            filters.get("severity_counts") or filters.get("by_severity") or filters.get("drift_counts_by_severity") or []
        )

    if not account_counts:
        account_counts = _normalize_account_rows(
            filters.get("account_counts") or filters.get("by_account") or filters.get("drift_counts_by_account") or []
        )

    if not day_counts:
        day_counts = _normalize_day_rows(
            filters.get("daily_counts") or filters.get("by_day") or filters.get("day_counts") or filters.get("drift_counts_by_day") or []
        )

    total_drift = sum(severity_counts.values())
    if total_drift == 0 and account_counts:
        total_drift = sum(item.get("count", 0) for item in account_counts)

    try:
        resource_count = len(crud_resource.list_filtered(db, limit=1)) if db is not None else 0
    except Exception:
        resource_count = 0

    payload: Dict[str, Any] = {
        "total_drift": total_drift,
        "by_severity": severity_counts,
        "by_account": account_counts,
        "by_day": day_counts,
        "severity_counts": severity_counts,
        "account_counts": account_counts,
        "daily_counts": day_counts,
        "resource_count": resource_count,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    return payload


def aggregate_summary(filters: Optional[Mapping[str, Any]] = None, db: Any = None) -> Dict[str, Any]:
    return aggregate(filters, db=db)


def get_summary(filters: Optional[Mapping[str, Any]] = None, db: Any = None) -> Dict[str, Any]:
    return aggregate(filters, db=db)


def summarize(filters: Optional[Mapping[str, Any]] = None, db: Any = None) -> Dict[str, Any]:
    return aggregate(filters, db=db)
