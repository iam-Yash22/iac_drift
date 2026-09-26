from typing import Any, Dict, List, Optional
import inspect

from sqlalchemy.orm import Session

import app.crud.crud_alert as crud_alert
import app.alerts.base as alerts_base
import app.alerts.email_channel as email_channel
import app.alerts.slack_channel as slack_channel
import app.alerts.sns_channel as sns_channel
import app.alerts.webhook_channel as webhook_channel
import app.core.events as events
import app.schemas.alert as alert_schemas
import app.utils.exceptions as exceptions


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def list_rules(db: Session, account_id: Optional[int] = None) -> List[Any]:
    """Return configured alert rules, optionally filtered by account."""
    try:
        # Try to list rules with account filtering
        if account_id is not None:
            rules = crud_alert.crud_alert_rule.list_by_account(db, account_id=account_id, active_only=False)
        else:
            rules = crud_alert.crud_alert_rule.list_rules(db, active_only=False)
        return rules
    except (AttributeError, TypeError):
        # Fallback to unfiltered list
        return crud_alert.crud_alert_rule.list_rules(db, active_only=False)


def create_rule(
    db: Session,
    rule_in: alert_schemas.AlertRuleCreate,
    account_id: Optional[int] = None,
) -> alert_schemas.AlertRuleOut:
    """Create a new alert rule scoped to an account."""
    rule_data = rule_in.dict() if hasattr(rule_in, "dict") else dict(rule_in)
    if account_id is not None:
        rule_data["account_id"] = account_id
    
    try:
        created = crud_alert.crud_alert_rule.create(db, obj_in=rule_data)
        return alert_schemas.AlertRuleOut.model_validate(created)
    except Exception as exc:
        raise exceptions.ServiceError(f"Failed to create alert rule: {exc}") from exc


def update_rule(
    db: Session,
    rule_id: int,
    rule_in: alert_schemas.AlertRuleUpdate,
    current_user: Optional[Any] = None,
) -> alert_schemas.AlertRuleOut:
    """Update an existing alert rule."""
    try:
        existing = crud_alert.crud_alert_rule.get(db, rule_id)
        if existing is None:
            raise exceptions.NotFoundError(f"Alert rule {rule_id} not found")
        
        update_data = rule_in.dict(exclude_unset=True) if hasattr(rule_in, "dict") else dict(rule_in)
        updated = crud_alert.crud_alert_rule.update(db, db_obj=existing, obj_in=update_data)
        return alert_schemas.AlertRuleOut.model_validate(updated)
    except exceptions.NotFoundError:
        raise
    except Exception as exc:
        raise exceptions.ServiceError(f"Failed to update alert rule: {exc}") from exc


def delete_rule(
    db: Session,
    rule_id: int,
    current_user: Optional[Any] = None,
) -> None:
    """Delete an existing alert rule."""
    try:
        existing = crud_alert.crud_alert_rule.get(db, rule_id)
        if existing is None:
            raise exceptions.NotFoundError(f"Alert rule {rule_id} not found")
        
        crud_alert.crud_alert_rule.remove(db, id=rule_id)
    except exceptions.NotFoundError:
        raise
    except Exception as exc:
        raise exceptions.ServiceError(f"Failed to delete alert rule: {exc}") from exc


def _call_first(module: Any, candidates: List[str], *args, **kwargs):
    for name in candidates:
        fn = getattr(module, name, None)
        if callable(fn):
            return fn(*args, **kwargs)
    raise AttributeError(f"None of {candidates} found on module {module}")


async def _call_first_async(module: Any, candidates: List[str], *args, **kwargs) -> Any:
    try:
        res = _call_first(module, candidates, *args, **kwargs)
    except AttributeError:
        return None
    return await _maybe_await(res)


def _matches_rule_using_base(rule: Any, event_payload: Dict[str, Any]) -> Optional[bool]:
    # Prefer a project-provided evaluator in alerts.base
    for name in ("evaluate_rule", "matches", "match_rule"):
        fn = getattr(alerts_base, name, None)
        if callable(fn):
            try:
                return fn(rule, event_payload)
            except Exception:
                return None
    return None


def _simple_rule_match(rule: Any, event_payload: Dict[str, Any]) -> bool:
    # Best-effort simple matching: resource_types intersection
    comp = event_payload.get("comparison") or {}
    rule_rt = None
    if isinstance(rule, dict):
        rule_rt = rule.get("resource_types")
    elif hasattr(rule, "resource_types"):
        rule_rt = getattr(rule, "resource_types")

    if not rule_rt:
        # no constraints -> match
        return True

    if isinstance(comp, dict):
        keys = set(comp.keys())
        if keys & set(rule_rt):
            return True
    return False


async def _load_active_rules() -> List[Any]:
    # Try common function names on crud_alert
    candidates = ["get_active", "list_active", "get_active_rules", "list", "all"]
    for name in candidates:
        fn = getattr(crud_alert, name, None)
        if callable(fn):
            res = fn()
            return await _maybe_await(res)
    # fallback: try `fetch`
    fn = getattr(crud_alert, "fetch", None)
    if callable(fn):
        return await _maybe_await(fn())
    return []


async def _dispatch_to_channel(channel_module: Any, rule: Any, event_payload: Dict[str, Any]) -> None:
    # Try common sender function names
    for name in ("send", "publish", "notify", "dispatch"):
        fn = getattr(channel_module, name, None)
        if callable(fn):
            try:
                res = fn(rule, event_payload)
                await _maybe_await(res)
            except Exception:
                # swallow channel errors to avoid failing entire dispatch
                pass
            return


async def _dispatch_for_rule(rule: Any, event_payload: Dict[str, Any]) -> None:
    # Determine whether rule matches
    matched = _matches_rule_using_base(rule, event_payload)
    if matched is None:
        matched = _simple_rule_match(rule, event_payload)
    if not matched:
        return

    # Determine channels from rule
    channels = None
    if isinstance(rule, dict):
        channels = rule.get("channels") or rule.get("alert_channels")
    elif hasattr(rule, "channels"):
        channels = getattr(rule, "channels")

    if not channels:
        # default to email if none specified
        channels = ["email"]

    channel_map = {
        "email": email_channel,
        "slack": slack_channel,
        "sns": sns_channel,
        "webhook": webhook_channel,
    }

    for ch in channels:
        mod = channel_map.get(ch)
        if mod:
            await _dispatch_to_channel(mod, rule, event_payload)


async def _handle_drift_event(event_payload: Dict[str, Any]) -> None:
    try:
        rules = await _load_active_rules()
    except Exception:
        rules = []

    for rule in rules:
        try:
            await _dispatch_for_rule(rule, event_payload)
        except Exception:
            # continue with other rules
            pass


def _register_handler() -> None:
    # Try multiple subscription APIs on core.events
    handler = lambda payload: _maybe_await(_handle_drift_event(payload))
    for name in ("subscribe", "on", "register_listener", "add_listener"):
        fn = getattr(events, name, None)
        if callable(fn):
            try:
                fn("DriftDetectedEvent", handler)
                return
            except Exception:
                continue


def init() -> None:
    """Initialize the alert dispatch service by registering the event handler."""
    _register_handler()


__all__ = ["init"]
