"""Aggregate v1 API routes."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
	accounts,
	alerts,
	auth,
	dashboard,
	drift,
	health,
	notifications,
	reports,
	resources,
	users,
	webhooks,
)

router = APIRouter()

router.include_router(accounts.router)
router.include_router(alerts.router)
router.include_router(auth.router)
router.include_router(dashboard.router)
router.include_router(drift.router)
router.include_router(health.router)
router.include_router(notifications.router)
router.include_router(reports.router)
router.include_router(resources.router)
router.include_router(users.router)
router.include_router(webhooks.router)
