from pathlib import Path
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import asyncio
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
import re
import smtplib
import subprocess
from typing import Any, Dict, List, Optional, Tuple
import inspect
from email.message import EmailMessage

from fastapi import BackgroundTasks
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.crud.crud_account as crud_account
import app.crud.crud_resource as crud_resource
import app.crud.crud_drift as crud_drift
import app.parsers.hcl_parser as hcl_parser
import app.parsers.terraform as terraform_parser
import app.parsers.aws as aws_parser
import app.parsers.normalizer as normalizer
import app.drift.engine as drift_engine
import app.services.aws_client_factory as aws_client_factory
import app.services.aws_resource_fetchers as aws_resource_fetchers
import app.core.events as events
import app.schemas.drift as drift_schemas
import app.utils.exceptions as exceptions
from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.scan import Scan
from app.models.alert import Alert


logger = get_logger(__name__)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _run_scan_background(*args: Any, **kwargs: Any) -> None:
    try:
        await orchestrate_account_scan(*args, **kwargs)
    except Exception:
        logger.error("Background account scan failed", exc_info=True)


def _drift_items(comparison: Any) -> List[Dict[str, Any]]:
    if isinstance(comparison, dict):
        drifts = comparison.get("drifts")
        if isinstance(drifts, list):
            return [item for item in drifts if isinstance(item, dict)]
        if {"resource_id", "resource_type", "is_drifted", "severity", "diffs", "summary"}.issubset(comparison):
            return [comparison]
    if isinstance(comparison, (list, tuple)):
        return [
            asdict(item) if is_dataclass(item) else item
            for item in comparison
            if isinstance(item, dict) or is_dataclass(item)
        ]
    if is_dataclass(comparison):
        return [asdict(comparison)]
    return []


def _scan_result(comparison: Any, total_resources: int) -> Dict[str, Any]:
    drifts = _drift_items(comparison)
    severity_breakdown: Dict[str, int] = {}
    for item in drifts:
        severity = str(item.get("severity", "none"))
        severity_breakdown[severity] = severity_breakdown.get(severity, 0) + 1
    return jsonable_encoder({
        "summary": {
            "total_resources": total_resources,
            "drifted_resources": sum(1 for item in drifts if item.get("is_drifted", True)),
            "severity_breakdown": severity_breakdown,
        },
        "drifts": drifts,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    })


async def _send_alert_email(
    account_id: Any,
    resource_id: str,
    resource_type: str,
    severity: str,
    diffs: Dict[str, Any],
    owner_name: str = "there",
    scan_id: Any = "latest",
) -> None:
    address = settings.alert_sender_email or settings.gmail_address
    app_password = settings.alert_sender_app_password or settings.gmail_app_password
    if not address or not app_password:
        logger.info("alert email skipped resource_id=%s reason=missing_gmail_settings", resource_id)
        return

    recipient = os.getenv("ALERT_TEST_RECIPIENT") or address

    diff_lines = [
        f"- {key}: desired={value.get('desired')!r}, actual={value.get('actual')!r}"
        for key, value in diffs.items()
        if isinstance(value, dict)
    ]
    message = EmailMessage()
    message["Subject"] = f"IaC DriftWatch alert: {resource_id}"
    message["From"] = address
    message["To"] = recipient
    message.set_content(
        f"Hi {owner_name}, drift was detected on account {account_id}.\n\n"
        f"View scan details: {settings.app_base_url}/accounts/{account_id}/scans/{scan_id}\n\n"
        f"Account ID: {account_id}\n"
        f"Resource ID: {resource_id}\n"
        f"Resource type: {resource_type}\n"
        f"Severity: {severity}\n\n"
        "Diffs:\n"
        + ("\n".join(diff_lines) if diff_lines else "- None")
    )
    logger.info("alert email body resource_id=%s body=%s", resource_id, message.get_content().strip())

    def send() -> None:
        debug_output = StringIO()
        try:
            with redirect_stdout(debug_output), redirect_stderr(debug_output):
                with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
                    smtp.set_debuglevel(1)
                    smtp.starttls()
                    smtp.login(address, app_password.get_secret_value())
                    smtp.send_message(message)
        finally:
            auth_exchange = False
            for line in debug_output.getvalue().splitlines():
                if re.search(r"send:\s+['\"]?AUTH\b", line, re.IGNORECASE):
                    auth_exchange = True
                    line = re.sub(r"(send:\s+).*$", r"\1[REDACTED]", line, flags=re.IGNORECASE)
                elif auth_exchange and re.search(r"(?:send:|reply:)", line, re.IGNORECASE):
                    auth_complete = bool(re.search(r"reply:\s+235\b", line, re.IGNORECASE))
                    line = re.sub(r"(send:|reply:).*$", r"\1 [REDACTED]", line, flags=re.IGNORECASE)
                    if auth_complete:
                        auth_exchange = False
                elif re.search(r"password|secret", line, re.IGNORECASE):
                    line = re.sub(r"(password|secret)([=: ]+).*$", r"\1\2[REDACTED]", line, flags=re.IGNORECASE)
                logger.info("smtp debug %s", line)

    try:
        await asyncio.to_thread(send)
        logger.info("alert email sent resource_id=%s", resource_id)
    except Exception:
        logger.error("alert email failed resource_id=%s", resource_id, exc_info=True)


def trigger_account_scan(
    background_tasks: BackgroundTasks,
    db: Session,
    account_id: int,
    scan_id: Optional[int] = None,
    triggered_by_id: Optional[int] = None,
) -> Scan:
    """Queue a scan for one account after the request has been accepted."""
    scan: Optional[Scan] = None
    if scan_id is None:
        scan = Scan(
            account_id=account_id,
            status="queued",
            triggered_by_id=triggered_by_id,
        )
        db.add(scan)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ValueError("scan already in progress for this account") from exc
        db.refresh(scan)
        scan_id = scan.id
    else:
        scan = db.get(Scan, scan_id)
    kwargs = {"db": db}
    kwargs["scan_id"] = scan_id
    background_tasks.add_task(_run_scan_background, str(account_id), "manual", **kwargs)
    return scan


def trigger_fleet_scan(
    background_tasks: BackgroundTasks,
    db: Session,
    triggered_by_id: Optional[int] = None,
) -> Dict[str, List[int]]:
    """Queue scans for all active accounts while skipping any already in progress."""
    accounts = crud_account.crud_account.get_active(db)
    results = {"queued": [], "skipped": []}
    for account in accounts:
        try:
            trigger_account_scan(
                background_tasks,
                db,
                account.id,
                triggered_by_id=triggered_by_id,
            )
            results["queued"].append(account.id)
        except ValueError:
            results["skipped"].append(account.id)
    return results


def list_drift(db: Session, account_id: Optional[int] = None) -> List[Any]:
    """Return drift records, optionally limited to one account."""
    if account_id is None:
        return crud_drift.crud_drift.get_multi(db)
    return crud_drift.crud_drift.list_for_account(db, account_id=account_id)


def _choose_and_call(module: Any, candidates: List[str], *args, **kwargs):
    """Call the first available attribute name in `candidates` on `module`.

    Returns the result of the call (may be awaitable). Raises AttributeError if none found.
    """
    for name in candidates:
        fn = getattr(module, name, None)
        if callable(fn):
            return fn(*args, **kwargs)
    raise AttributeError(f"None of {candidates} found on module {module}")


async def _call_available(module: Any, candidates: List[str], *args, **kwargs) -> Any:
    try:
        result = _choose_and_call(module, candidates, *args, **kwargs)
    except AttributeError:
        return None
    return await _maybe_await(result)


def _state_resource_to_baseline(resource: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert one Terraform state resource into a comparison baseline."""
    if resource.get("mode") == "data":
        return None
    resource_type = resource.get("type")
    type_map = {
        "aws_instance": "ec2_instance",
        "aws_s3_bucket": "s3_bucket",
        "aws_iam_role": "iam_role",
        "aws_security_group": "security_group",
        "aws_lambda_function": "lambda_function",
        "aws_elastic_beanstalk_environment": "elastic_beanstalk_environment",
    }
    normalized_type = type_map.get(resource_type, resource_type)
    instances = resource.get("instances") or []
    attributes = instances[0].get("attributes", {}) if instances else resource.get("values", {})
    if not isinstance(attributes, dict) or not normalized_type:
        return None

    arn = attributes.get("arn") or attributes.get("function_arn") or attributes.get("environment_arn")
    name = (
        attributes.get("name")
        or attributes.get("bucket")
        or attributes.get("function_name")
        or attributes.get("environment_name")
        or (attributes.get("tags") or {}).get("Name")
        or resource.get("name")
    )
    resource_id = (
        attributes.get("unique_id")
        or (arn if normalized_type in {"s3_bucket", "lambda_function", "elastic_beanstalk_environment"} else None)
        or attributes.get("id")
        or name
    )
    if not resource_id or not name:
        return None
    baseline = {
        "resource_type": normalized_type,
        "resource_name": str(name),
        "resource_id": str(resource_id),
        "arn": arn,
        "region": attributes.get("region"),
        "tags": attributes.get("tags") or attributes.get("tags_all") or {},
        "attributes": attributes,
        "raw": resource,
    }
    if normalized_type == "lambda_function":
        baseline["FunctionName"] = name
        baseline["FunctionArn"] = arn
    elif normalized_type == "elastic_beanstalk_environment":
        baseline["EnvironmentId"] = resource_id
        baseline["EnvironmentArn"] = arn
        baseline["EnvironmentName"] = name
    return baseline


def _state_document_resources(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    resources: List[Dict[str, Any]] = []
    for resource in document.get("resources", []):
        baseline = _state_resource_to_baseline(resource)
        if baseline:
            resources.append(baseline)
    root_module = document.get("values", {}).get("root_module", {})
    for resource in root_module.get("resources", []):
        baseline = _state_resource_to_baseline(resource)
        if baseline:
            resources.append(baseline)
    return resources


def _load_terraform_reference(account_id: int, db: Session) -> List[Any]:
    """Load applied resource values from Terraform state, not raw .tf source."""
    from app.models.account import AwsAccount
    from app.models.terraform_baseline import TerraformBaseline

    baseline_rows = (
        db.query(TerraformBaseline)
        .filter(TerraformBaseline.account_id == int(account_id))
        .order_by(TerraformBaseline.id)
        .all()
    )
    if baseline_rows:
        resource_payloads: List[Dict[str, Any]] = []
        for row in baseline_rows:
            payload = {
                "resource_type": row.resource_type,
                "resource_name": row.name,
                "resource_id": row.resource_id,
                "arn": row.arn,
                "region": row.region,
                "tags": row.tags or {},
                "attributes": row.configuration or {},
            }
            if row.resource_type == "lambda_function":
                payload["FunctionName"] = row.name or row.resource_id
                payload["FunctionArn"] = row.arn
            elif row.resource_type == "elastic_beanstalk_environment":
                payload["EnvironmentId"] = row.resource_id
                payload["EnvironmentArn"] = row.arn
                payload["EnvironmentName"] = row.name or row.resource_id
            resource_payloads.append(payload)
        return normalizer.normalize_resources(resource_payloads)

    if db.query(AwsAccount).count() != 1:
        raise ValueError(f"No Terraform baseline ingested for account {account_id}")

    root = Path(__file__).resolve().parents[2] / "terraform"
    if not root.exists():
        return []

    documents: List[Dict[str, Any]] = []
    try:
        completed = subprocess.run(
            ["terraform", "show", "-json"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        documents.append(json.loads(completed.stdout))
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass

    state_path = root / "terraform.tfstate"
    if not documents and state_path.exists():
        try:
            documents.append(json.loads(state_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass

    reference: List[Any] = []
    for document in documents:
        reference.extend(_state_document_resources(document))
    if reference:
        return normalizer.normalize_resources(reference)
    return []


def _coerce_account_id(value: Any) -> Any:
    if value is None:
        return value
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
            return int(stripped)
        return value
    if isinstance(value, (float,)):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


async def orchestrate_account_scan(account_id: str, trigger: str = "scheduled", db: Session | None = None, scan_id: Optional[int] = None) -> Dict[str, Any]:
    """Coordinate a scan for the given account.

    Steps:
    - load account from the database
    - load the Terraform reference from /terraform
    - create AWS clients and fetch live resources from that account
    - normalize and compare live vs desired values
    - persist resources and drift results
    - publish `DriftDetectedEvent` when drift detected
    """
    if db is None:
        from app.db.session import SessionLocal
        db = SessionLocal()
        close_db = True
    else:
        close_db = False

    try:
        scan = db.get(Scan, scan_id) if scan_id is not None else None
        if scan is not None:
            scan.status = "running"
            db.commit()

        account = await _call_available(crud_account, ["get_by_id", "get", "retrieve"], account_id)
        if account is None and db is not None:
            try:
                account = crud_account.crud_account.get(db, id=int(account_id))
            except (TypeError, ValueError):
                account = None
        if account is None:
            raise exceptions.NotFoundError(f"Account not found: {account_id}")

        raw_account_id = getattr(account, "id", account_id)
        resolved_account_id = _coerce_account_id(raw_account_id)
        if not isinstance(resolved_account_id, (int, str, float, bool)):
            resolved_account_id = account_id

        # Reference infrastructure is pulled from the Terraform files in /terraform.
        tf_resources = _load_terraform_reference(int(resolved_account_id), db)
        if not tf_resources:
            tf_resources = await _call_available(terraform_parser, ["normalize_resources", "parse_resources"], None)

        # Prepare AWS clients
        clients = await _maybe_await(aws_client_factory.get_clients_for_account(account))

        # Fetch live resources using fetchers
        live_raw: Dict[str, Any] = {}
        try:
            ec2 = clients.get("ec2") if isinstance(clients, dict) else clients
            if ec2:
                live_raw["ec2_instances"] = await _maybe_await(aws_resource_fetchers.fetch_ec2_instances(ec2))

            s3 = clients.get("s3") if isinstance(clients, dict) else None
            if s3:
                live_raw["s3_buckets"] = await _maybe_await(aws_resource_fetchers.fetch_s3_buckets(s3))

            iam = clients.get("iam") if isinstance(clients, dict) else None
            if iam:
                live_raw["iam_roles"] = await _maybe_await(aws_resource_fetchers.fetch_iam_roles(iam))

            rds = clients.get("rds") if isinstance(clients, dict) else None
            if rds:
                live_raw["rds_instances"] = await _maybe_await(aws_resource_fetchers.fetch_rds_instances(rds))

            if ec2:
                live_raw["security_groups"] = await _maybe_await(aws_resource_fetchers.fetch_security_groups(ec2))

            lambda_client = clients.get("lambda") if isinstance(clients, dict) else None
            if lambda_client:
                live_raw["lambda_functions"] = await _maybe_await(
                    aws_resource_fetchers.fetch_lambda_functions(lambda_client)
                )

            elastic_beanstalk = clients.get("elasticbeanstalk") if isinstance(clients, dict) else None
            if elastic_beanstalk:
                live_raw["elastic_beanstalk_environments"] = await _maybe_await(
                    aws_resource_fetchers.fetch_elastic_beanstalk_environments(elastic_beanstalk)
                )
        except Exception as exc:
            raise exceptions.ServiceError(f"Failed to fetch live resources: {exc}") from exc

        # Normalize live resources (best-effort)
        live_resources = await _call_available(aws_parser, ["normalize_live_resources", "parse_live_resources"], live_raw)
        if live_resources is None:
            live_resources = live_raw

        # Compare
        try:
            comparison = await _maybe_await(drift_engine.compare_resources(tf_resources, live_resources))
        except Exception as exc:
            raise exceptions.ServiceError(f"Drift comparison failed: {exc}") from exc

        # Persist resources for the owning account in the database.
        resource_store = getattr(crud_resource, "crud_resource", crud_resource)
        try:
            module_upsert = getattr(crud_resource, "upsert_many", None)
            if callable(module_upsert):
                result = module_upsert(db, account_id=resolved_account_id, resources=live_resources)
                if inspect.isawaitable(result):
                    await result
            else:
                result = getattr(resource_store, "upsert_many", None)
                if result is not None:
                    payload = result(db, account_id=resolved_account_id, resources=live_resources)
                    if inspect.isawaitable(payload):
                        await payload
        except Exception:
            db.rollback()
            logger.error(
                "Failed to persist discovered resources for account %s",
                resolved_account_id,
                exc_info=True,
            )

        # Persist drift results
        try:
            drift_model = crud_drift.crud_drift.model
            alertable_resource_ids: set[str] = set()
            latest_drift_records: Dict[str, Any] = {}
            for item in _drift_items(comparison):
                resource_id = item.get("resource_id") or item.get("id")
                if resource_id is None:
                    continue
                tracked_resource = (
                    db.query(resource_store.model)
                    .filter(
                        resource_store.model.account_id == resolved_account_id,
                        resource_store.model.resource_id == str(resource_id),
                    )
                    .first()
                )
                if tracked_resource is None:
                    continue
                latest_drift_record = (
                    db.query(drift_model)
                    .filter(drift_model.tracked_resource_id == tracked_resource.id)
                    .order_by(drift_model.id.desc())
                    .first()
                )
                resource_key = str(resource_id)
                latest_drift_records[resource_key] = latest_drift_record
                if item.get("is_drifted", True):
                    if latest_drift_record is None or latest_drift_record.reconciled:
                        alertable_resource_ids.add(resource_key)
                elif latest_drift_record is not None and not latest_drift_record.reconciled:
                    latest_drift_record.reconciled = True

            drift_record = {
                "account_id": resolved_account_id,
                "trigger": trigger,
                "comparison": comparison,
            }
            drift_store = getattr(crud_drift, "crud_drift", crud_drift)
            module_create = getattr(crud_drift, "create", None)
            if callable(module_create):
                result = module_create(db, obj_in=drift_record)
                if inspect.isawaitable(result):
                    await result
            else:
                drift_items = _drift_items(comparison)
                for item in drift_items:
                    if not isinstance(item, dict):
                        continue
                    resource_id = item.get("resource_id") or item.get("id")
                    if resource_id is None:
                        continue
                    tracked_resource = (
                        db.query(resource_store.model)
                        .filter(
                            resource_store.model.account_id == resolved_account_id,
                            resource_store.model.resource_id == str(resource_id),
                        )
                        .first()
                    )
                    if tracked_resource is None:
                        continue
                    if item.get("is_drifted", True):
                        db.add(
                            crud_drift.crud_drift.model(
                                tracked_resource_id=tracked_resource.id,
                                change_type=str(item.get("change_type", "modified")),
                                diff=jsonable_encoder(item),
                                severity=str(item.get("severity", "low")),
                            )
                        )
                db.commit()

            drift_items = _drift_items(comparison)
            created_alerts: List[Dict[str, Any]] = []
            for item in drift_items:
                resource_id = item.get("resource_id") or item.get("id")
                if item.get("is_known_exception", False):
                    logger.info("alert skipped resource_id=%s reason=known_exception", resource_id)
                    continue
                if not item.get("is_drifted", True):
                    logger.info("alert skipped resource_id=%s reason=not_drifted", resource_id)
                    continue
                if resource_id is None:
                    logger.info("alert skipped resource_id=None reason=missing_resource_id")
                    continue
                if str(resource_id) not in alertable_resource_ids:
                    logger.info("alert skipped resource_id=%s reason=drift_unchanged", resource_id)
                    continue
                tracked_resource = (
                    db.query(resource_store.model)
                    .filter(
                        resource_store.model.account_id == resolved_account_id,
                        resource_store.model.resource_id == str(resource_id),
                    )
                    .first()
                )
                if tracked_resource is None:
                    logger.info("alert skipped resource_id=%s reason=tracked_resource_not_found", resource_id)
                    continue
                drift_record = latest_drift_records.get(str(resource_id))
                if drift_record is None:
                    drift_record = (
                        db.query(drift_model)
                        .filter(drift_model.tracked_resource_id == tracked_resource.id)
                        .order_by(drift_model.id.desc())
                        .first()
                    )
                if drift_record is None:
                    logger.info("alert skipped resource_id=%s reason=drift_record_not_found", resource_id)
                    continue
                owner = getattr(account, "owner", None)
                owner_name = (
                    getattr(owner, "username", None)
                    or getattr(owner, "email", None)
                    or "there"
                )
                db.add(
                    Alert(
                        account_id=resolved_account_id,
                        scan_id=scan.id if scan is not None else None,
                        drift_record_id=drift_record.id,
                        resource_id=str(resource_id),
                        resource_type=str(item.get("resource_type", "unknown")),
                        severity=str(item.get("severity", "low")),
                        diffs=jsonable_encoder(item.get("diffs", {})),
                        summary=str(item.get("summary", "Drift detected.")),
                    )
                )
                created_alerts.append(
                    {
                        "resource_id": str(resource_id),
                        "resource_type": str(item.get("resource_type", "unknown")),
                        "severity": str(item.get("severity", "low")),
                        "diffs": jsonable_encoder(item.get("diffs", {})),
                        "owner_name": owner_name,
                        "scan_id": scan.id if scan is not None else "latest",
                    }
                )
                logger.info("alert created resource_id=%s", resource_id)
            db.commit()
            for alert in created_alerts:
                await _send_alert_email(resolved_account_id, **alert)
        except Exception as exc:
            logger.error("alert creation failed", exc_info=True)
            raise exceptions.ServiceError("Failed to persist drift results") from exc

        # Publish event if drift detected
        try:
            drift_detected = False
            if isinstance(comparison, dict):
                drift_detected = bool(comparison.get("drifts") or comparison.get("differences"))
            elif isinstance(comparison, list):
                drift_detected = len(comparison) > 0

            if drift_detected:
                evt_payload = {"account_id": resolved_account_id, "comparison": comparison}
                pub = getattr(events, "publish", None) or getattr(events, "emit", None) or getattr(events, "publish_event", None)
                if callable(pub):
                    pub("DriftDetectedEvent", evt_payload)
        except Exception:
            pass

        if scan is not None:
            scan.result = _scan_result(comparison, len(live_resources))
            scan.status = "completed"
            db.commit()
        return {"account_id": resolved_account_id, "comparison": comparison}
    except Exception as exc:
        if scan_id is not None:
            try:
                db.rollback()
                fresh_scan = db.get(Scan, scan_id)
                if fresh_scan is None:
                    fresh_scan = db.query(Scan).filter(Scan.id == scan_id).one_or_none()
                if fresh_scan is not None:
                    fresh_scan.status = "failed"
                    fresh_scan.error = str(exc)
                    db.commit()
            except Exception:
                db.rollback()
                logger.exception("Failed to mark scan as failed for account %s scan_id=%s", account_id, scan_id)
        raise
    finally:
        if close_db:
            db.close()
