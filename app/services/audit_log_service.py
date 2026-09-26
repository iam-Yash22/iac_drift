"""Offline, append-only audit events for administrative mutations."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_AUDIT_DB = Path(__file__).resolve().parents[2] / "logs" / "admin_actions.sqlite3"


def record_admin_action(
    *,
    actor_id: Any,
    action: str,
    target_type: str,
    target_id: Any,
    details: Mapping[str, Any] | None = None,
) -> None:
    """Persist one redacted administrative action immediately to local SQLite."""
    _AUDIT_DB.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    with sqlite3.connect(_AUDIT_DB, timeout=10) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                actor_id TEXT,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT,
                details_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO admin_actions
                (timestamp, actor_id, action, target_type, target_id, details_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                None if actor_id is None else str(actor_id),
                action,
                target_type,
                None if target_id is None else str(target_id),
                json.dumps(dict(details or {}), default=str, sort_keys=True),
            ),
        )
        connection.commit()
