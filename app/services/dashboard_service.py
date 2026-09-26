from typing import Any, Dict, Optional
import inspect
import json

import app.crud.crud_account as crud_account
import app.crud.crud_drift as crud_drift
import app.crud.crud_resource as crud_resource
import app.dashboard.aggregators as aggregators
import app.dashboard.cache as cache
import app.models.account as account_model
import app.schemas.drift as drift_schemas
import app.utils.exceptions as exceptions


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _make_cache_key(filters: Optional[Dict[str, Any]] = None) -> str:
    if not filters:
        return "dashboard:summary:all"
    try:
        return "dashboard:summary:" + json.dumps(filters, sort_keys=True, separators=(",", ":"))
    except Exception:
        return "dashboard:summary:custom"


async def _cache_get(key: str) -> Optional[Any]:
    for name in ("get", "read", "fetch", "get_value"):
        fn = getattr(cache, name, None)
        if callable(fn):
            try:
                return await _maybe_await(fn(key))
            except Exception:
                continue
    return None


async def _cache_set(key: str, value: Any, ttl: int) -> None:
    for name in ("set", "write", "put", "set_value"):
        fn = getattr(cache, name, None)
        if callable(fn):
            try:
                try:
                    res = fn(key, value, ttl)
                except TypeError:
                    res = fn(key, value)
                await _maybe_await(res)
                return
            except Exception:
                continue


def _resolve_account_id(db: Any, current_user: Any = None, account_id: Optional[int] = None) -> Optional[int]:
    """Resolve the canonical account row id for either a DB id or an AWS account id."""
    if account_id is not None:
        value = str(account_id).strip()
        if not value:
            return None

        candidate = (
            db.query(account_model.AwsAccount)
            .filter(account_model.AwsAccount.account_id == value)
            .first()
        )
        if candidate is not None:
            return int(candidate.id)

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    if current_user is None:
        return None

    user_id = getattr(current_user, "id", None)
    if user_id is None:
        user_id = getattr(current_user, "user_id", None)

    candidate = db.query(account_model.AwsAccount).order_by(account_model.AwsAccount.id.asc()).first()
    if candidate is not None:
        return int(candidate.id)

    owned_accounts = getattr(current_user, "aws_accounts", None)
    if owned_accounts:
        first_account = next(iter(owned_accounts), None)
        if first_account is not None:
            return int(first_account.id)

    account_attr = getattr(current_user, "account_id", None)
    if account_attr is not None:
        return int(account_attr)

    return None


def list_resources(
    db: Any,
    *,
    current_user: Any = None,
    account_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 20,
    resource_type: Optional[str] = None,
    since: Optional[Any] = None,
    **kwargs: Any,
) -> list[Any]:
    """Return tracked resources scoped to the current account when available."""
    resolved_account_id = _resolve_account_id(db, current_user=current_user, account_id=account_id)
    offset = max(0, (page - 1) * per_page)
    return crud_resource.crud_resource.list_filtered(
        db,
        account_id=resolved_account_id,
        resource_type=resource_type,
        since=since,
        limit=per_page,
        offset=offset,
    )


def get_summary(
    db: Any,
    *,
    current_user: Any = None,
    filters: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Return a dashboard summary payload compatible with the API endpoints."""
    resolved_filters: Dict[str, Any] = dict(filters or {})
    resolved_filters.update({k: v for k, v in kwargs.items() if v is not None})

    account_scope = _resolve_account_id(db, current_user=current_user, account_id=resolved_filters.get("account_id"))
    if account_scope is not None:
        resolved_filters["account_id"] = account_scope
    elif "account_id" in resolved_filters:
        resolved_filters.pop("account_id")

    return aggregators.aggregate(resolved_filters, db=db)


async def get_dashboard_summary(filters: Optional[Dict[str, Any]] = None, ttl_seconds: int = 30) -> Dict[str, Any]:
    """Return aggregated dashboard summary for the given filters."""
    key = _make_cache_key(filters)

    cached = await _cache_get(key)
    if cached is not None:
        return cached

    agg_candidates = ["aggregate", "aggregate_summary", "get_summary", "summarize"]
    agg_fn = None
    for name in agg_candidates:
        fn = getattr(aggregators, name, None)
        if callable(fn):
            agg_fn = fn
            break

    if not agg_fn:
        raise exceptions.ServiceError("No aggregator available in dashboard.aggregators")

    try:
        result = agg_fn(filters or {})
        summary = await _maybe_await(result)
    except Exception as exc:
        raise exceptions.ServiceError(f"Aggregator failed: {exc}") from exc

    if not isinstance(summary, dict):
        try:
            summary = dict(summary)
        except Exception:
            raise exceptions.ServiceError("Aggregator returned unsupported summary type")

    try:
        await _cache_set(key, summary, ttl_seconds)
    except Exception:
        pass

    return summary


def clear_cache() -> None:
    """Clear dashboard cache (best-effort)."""
    for name in ("clear", "flush", "reset"):
        fn = getattr(cache, name, None)
        if callable(fn):
            try:
                fn()
                return
            except Exception:
                continue


__all__ = ["list_resources", "get_summary", "get_dashboard_summary", "clear_cache"]
