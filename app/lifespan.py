"""Application lifespan hooks.

Registered in ``app.factory.create_app`` and executed once per process:

* **Startup** — configure logging, verify database connectivity.
* **Shutdown** — dispose the SQLAlchemy engine and release pool connections.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from app.core.config import DEFAULT_BOOTSTRAP_ADMIN_PASSWORD, settings
from app.core.logging_config import configure_logging, get_logger
from app.db.init_db import init_db
from app.db.session import check_db_connectivity, dispose_engine
from app.db.session import SessionLocal
from app.models.account import AwsAccount
from app.models.scan import Scan
from app.services.drift_orchestrator import _run_scan_background


def _scan_interval_minutes() -> int:
    try:
        interval = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))
    except ValueError:
        return 15
    return max(interval, 1)


async def _run_scheduled_scan(account_id: int) -> None:
    with SessionLocal() as db:
        scan = Scan(account_id=account_id, status="queued")
        db.add(scan)
        db.commit()
        db.refresh(scan)
        await _run_scan_background(str(account_id), "scheduled", db=db, scan_id=scan.id)


def _configure_scan_scheduler(scheduler: AsyncIOScheduler, logger: object) -> None:
    interval_minutes = _scan_interval_minutes()
    with SessionLocal() as db:
        accounts = db.query(AwsAccount).all()

    for account in accounts:
        scheduler.add_job(
            _run_scheduled_scan,
            trigger="interval",
            minutes=interval_minutes,
            args=[account.id],
            id=f"account_scan_{account.id}",
            replace_existing=True,
        )
    logger.info(
        "account scan scheduler configured",
        extra={"account_count": len(accounts), "interval_minutes": interval_minutes},
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and graceful shutdown lifecycle hooks."""
    configure_logging()
    logger = get_logger(__name__)

    logger.info(
        "application starting",
        extra={
            "environment": settings.app.environment,
            "version": settings.app.version,
        },
    )

    await asyncio.to_thread(check_db_connectivity)
    logger.info("database connectivity verified")

    if settings.app.environment != "development":
        admin_password = settings.admin_password.get_secret_value() if settings.admin_password else ""
        if not admin_password.strip() or admin_password == DEFAULT_BOOTSTRAP_ADMIN_PASSWORD:
            raise RuntimeError("ADMIN_PASSWORD must be set and must not equal the default bootstrap password outside development")

    with SessionLocal() as db:
        init_db(db)
        stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.scan_stale_minutes)
        stale_scans = (
            db.query(Scan)
            .filter(Scan.status.in_(["queued", "running"]))
            .filter(Scan.updated_at < stale_cutoff)
            .all()
        )
        for scan in stale_scans:
            scan.status = "failed"
            scan.error = "orphaned"
        if stale_scans:
            db.commit()
            logger.warning(
                "recovered stale scans",
                extra={"count": len(stale_scans), "cutoff": stale_cutoff.isoformat()},
            )
    logger.info("database bootstrap complete")

    scheduler = AsyncIOScheduler()
    _configure_scan_scheduler(scheduler, logger)
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("account scan scheduler started")

    try:
        yield
    finally:
        scheduler.shutdown()
        logger.info("account scan scheduler stopped")

        await asyncio.to_thread(dispose_engine)
        logger.info("database engine disposed")
