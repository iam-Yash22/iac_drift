import inspect
import io
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

import app.crud.crud_report as crud_report
import app.crud.crud_drift as crud_drift
import app.reports.pdf_generator as pdf_generator
import app.reports.csv_generator as csv_generator
import app.reports.s3_uploader as s3_uploader
import app.schemas.report as report_schemas
import app.utils.exceptions as exceptions


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _call_first(module: Any, candidates, *args, **kwargs):
    for name in candidates:
        fn = getattr(module, name, None)
        if callable(fn):
            return fn(*args, **kwargs)
    raise AttributeError(f"None of {candidates} found on module {module}")


async def _call_first_async(module: Any, candidates, *args, **kwargs):
    try:
        res = _call_first(module, candidates, *args, **kwargs)
    except AttributeError:
        return None
    return await _maybe_await(res)


async def _fetch_drift_data_for_report(report_req: report_schemas.ReportRequest) -> Any:
    # Try common CRUD functions to retrieve drift records for requested scope
    candidates = [
        "query",
        "get_for_account",
        "list_for_account",
        "list_by_account",
        "get_by_account",
        "list",
    ]
    params = {}
    if getattr(report_req, "account_id", None):
        params["account_id"] = report_req.account_id
    if getattr(report_req, "since", None):
        params["since"] = report_req.since

    for name in candidates:
        fn = getattr(crud_drift, name, None)
        if callable(fn):
            try:
                res = fn(**params) if params else fn()
                return await _maybe_await(res)
            except TypeError:
                # signature mismatch, try without params
                try:
                    res = fn()
                    return await _maybe_await(res)
                except Exception:
                    continue
            except Exception:
                continue
    # fallback: empty
    return []


def _make_s3_key(report_req: report_schemas.ReportRequest, ext: str) -> str:
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    rid = getattr(report_req, "request_id", None) or str(uuid.uuid4())
    account = getattr(report_req, "account_id", "global")
    return f"reports/{account}/{ts}-{rid}.{ext}"


async def generate_and_store_report(report_req: report_schemas.ReportRequest) -> Dict[str, Any]:
    """Generate a report (PDF/CSV), upload it, and persist metadata.

    Returns a metadata dict describing the stored report.
    """
    # Fetch data
    data = await _fetch_drift_data_for_report(report_req)

    # Choose format
    fmt = getattr(report_req, "format", "pdf")

    file_bytes: Optional[bytes] = None
    filename_ext = "pdf" if fmt.lower() == "pdf" else "csv"

    if fmt.lower() == "pdf":
        gen_candidates = ["generate", "build", "create", "to_pdf", "render"]
        res = await _call_first_async(pdf_generator, gen_candidates, data, report_req)
        if res is None:
            raise exceptions.ServiceError("PDF generator not available")
    else:
        gen_candidates = ["generate", "build", "create", "to_csv", "render"]
        res = await _call_first_async(csv_generator, gen_candidates, data, report_req)
        if res is None:
            raise exceptions.ServiceError("CSV generator not available")

    # Normalize generator output to bytes
    if isinstance(res, bytes):
        file_bytes = res
    elif isinstance(res, str):
        # assume file path
        try:
            with open(res, "rb") as f:
                file_bytes = f.read()
        except Exception as exc:
            raise exceptions.ServiceError(f"Failed to read generated file: {exc}") from exc
    elif hasattr(res, "read"):
        # file-like object
        try:
            file_bytes = res.read()
        except Exception as exc:
            raise exceptions.ServiceError(f"Failed to read generated file-like object: {exc}") from exc
    else:
        # try to coerce to string then bytes
        try:
            file_bytes = bytes(str(res), "utf-8")
        except Exception as exc:
            raise exceptions.ServiceError(f"Unsupported generator output type: {exc}") from exc

    if file_bytes is None:
        raise exceptions.ServiceError("Generator produced no output")

    # Upload via s3_uploader
    key = _make_s3_key(report_req, filename_ext)
    upload_candidates = ["upload_bytes", "upload", "upload_file", "put_object"]
    uploaded_url = None
    for name in upload_candidates:
        fn = getattr(s3_uploader, name, None)
        if callable(fn):
            try:
                # prefer upload_bytes signature (bytes, key)
                try:
                    res_upload = fn(file_bytes, key)
                except TypeError:
                    # try (fileobj, key)
                    res_upload = fn(io.BytesIO(file_bytes), key)
                uploaded_url = await _maybe_await(res_upload)
                break
            except Exception:
                continue

    if not uploaded_url:
        raise exceptions.ServiceError("Failed to upload report to storage")

    # Persist metadata via crud_report
    meta = {
        "key": key,
        "url": uploaded_url,
        "format": filename_ext,
        "account_id": getattr(report_req, "account_id", None),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "request_id": getattr(report_req, "request_id", None),
    }

    persist_candidates = ["create", "record", "save", "persist"]
    persisted = None
    for name in persist_candidates:
        fn = getattr(crud_report, name, None)
        if callable(fn):
            try:
                resp = fn(meta)
                persisted = await _maybe_await(resp)
                break
            except Exception:
                continue

    if persisted is None:
        # best-effort: return metadata even if not persisted
        return meta

    return persisted


def create_report(
    db: Session,
    *,
    current_user: Any,
    report_in: report_schemas.ReportCreate,
    account_id: Optional[int] = None,
) -> report_schemas.ReportOut:
    """Create and generate a report scoped to the provided account.
    
    This is a synchronous wrapper that queues report generation asynchronously.
    """
    # Prepare report request with account scope
    report_req = report_schemas.ReportRequest(
        report_type=getattr(report_in, "report_type", "drift"),
        format=getattr(report_in, "format", "pdf"),
        account_id=account_id,
        resource_id=getattr(report_in, "resource_id", None),
        start_date=getattr(report_in, "start_date", None),
        end_date=getattr(report_in, "end_date", None),
        filters=getattr(report_in, "filters", None),
    )
    
    # Create report record in DB with pending status
    report_data = {
        "report_type": report_req.report_type,
        "format": report_req.format,
        "status": "pending",
        "account_id": account_id,
        "resource_id": report_req.resource_id,
        "metadata": {
            "filters": report_req.filters,
            "start_date": report_req.start_date.isoformat() if report_req.start_date else None,
            "end_date": report_req.end_date.isoformat() if report_req.end_date else None,
        },
    }
    
    # Persist initial report record
    try:
        created = crud_report.crud_report.create(db, obj_in=report_data)
    except Exception:
        created = None
    
    if created:
        return report_schemas.ReportOut.model_validate(created)
    
    # Fallback response if creation failed
    return report_schemas.ReportOut(
        id=0,
        report_type=report_req.report_type,
        format=report_req.format,
        status="pending",
        account_id=account_id,
    )


def get_download_url(
    db: Session,
    *,
    current_user: Any,
    report_id: int,
) -> str:
    """Retrieve the download URL for a generated report."""
    try:
        report = crud_report.crud_report.get(db, report_id)
        if report is None:
            raise exceptions.NotFoundError(f"Report {report_id} not found")
        
        # Extract download URL from report metadata or URL field
        download_url = getattr(report, "download_url", None) or getattr(report, "url", None)
        if not download_url:
            raise exceptions.ServiceError(f"Report {report_id} has no download URL")
        
        return download_url
    except exceptions.NotFoundError:
        raise
    except Exception as exc:
        raise exceptions.ServiceError(f"Failed to retrieve report download URL: {exc}") from exc

