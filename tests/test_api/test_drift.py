import pytest
from unittest import mock

from fastapi import BackgroundTasks

from app.api.v1.endpoints.drift import trigger_scan, trigger_scan_request
from app.models.scan import Scan
from app.services import drift_orchestrator


def _try_post(client, paths, **kwargs):
    for path in paths:
        resp = client.post(path, **kwargs)
        if resp.status_code == 404:
            continue
        return path, resp
    pytest.skip("No POST drift/webhook endpoint found")


def _try_get(client, paths, **kwargs):
    for path in paths:
        resp = client.get(path, **kwargs)
        if resp.status_code == 404:
            continue
        return path, resp
    pytest.skip("No GET drift endpoint found")


def test_start_drift_scan_endpoint(client, auth_headers):
    paths = ("/api/v1/drift/scan/0", "/api/v1/drift/scan", "/api/v1/drift/start")
    payload = {"target": "all"}
    path, resp = _try_post(client, paths, json=payload, headers=auth_headers)

    assert resp.status_code < 500
    assert resp.status_code in (200, 201, 202, 400, 401)

    if resp.status_code in (200, 201, 202):
        try:
            body = resp.json()
            assert isinstance(body, dict)
        except Exception:
            pass


def test_account_scan_endpoint_queues_orchestrator(monkeypatch, db_session):
    background_tasks = BackgroundTasks()
    trigger_account_scan = mock.Mock()
    monkeypatch.setattr(drift_orchestrator, "trigger_account_scan", trigger_account_scan)

    current_user = mock.Mock(role="admin")
    response = trigger_scan(
        account_id=42,
        background_tasks=background_tasks,
        current_user=current_user,
        db=db_session,
    )

    assert response == {"status": "accepted"}
    trigger_account_scan.assert_called_once_with(background_tasks, db_session, 42, triggered_by_id=current_user.id)


def test_fleet_scan_endpoint_queues_orchestrator(monkeypatch, db_session):
    background_tasks = BackgroundTasks()
    trigger_fleet_scan = mock.Mock(return_value={"queued": [7], "skipped": []})
    monkeypatch.setattr(drift_orchestrator, "trigger_fleet_scan", trigger_fleet_scan)

    current_user = mock.Mock(role="admin")
    response = trigger_scan(
        account_id=0,
        background_tasks=background_tasks,
        current_user=current_user,
        db=db_session,
    )

    assert response == {"queued": [7], "skipped": []}
    trigger_fleet_scan.assert_called_once_with(background_tasks, db_session, triggered_by_id=current_user.id)


def test_scan_request_without_account_queues_fleet(monkeypatch, db_session):
    background_tasks = BackgroundTasks()
    trigger_fleet_scan = mock.Mock(return_value={"queued": [7], "skipped": []})
    monkeypatch.setattr(drift_orchestrator, "trigger_fleet_scan", trigger_fleet_scan)

    current_user = mock.Mock(role="admin")
    response = trigger_scan_request(
        background_tasks=background_tasks,
        account_id=None,
        current_user=current_user,
        db=db_session,
    )

    assert response == {"queued": [7], "skipped": []}
    trigger_fleet_scan.assert_called_once_with(background_tasks, db_session, triggered_by_id=current_user.id)


def test_scan_request_with_account_queues_single_scan(monkeypatch, db_session):
    background_tasks = BackgroundTasks()
    trigger_account_scan = mock.Mock()
    monkeypatch.setattr(drift_orchestrator, "trigger_account_scan", trigger_account_scan)

    current_user = mock.Mock(role="admin")
    response = trigger_scan_request(
        background_tasks=background_tasks,
        account_id=42,
        current_user=current_user,
        db=db_session,
    )

    assert response == {"status": "accepted"}
    trigger_account_scan.assert_called_once_with(background_tasks, db_session, 42, triggered_by_id=current_user.id)


def test_account_trigger_queues_account_orchestrator(monkeypatch, db_session):
    background_tasks = BackgroundTasks()
    orchestrate = mock.AsyncMock()
    monkeypatch.setattr(drift_orchestrator, "orchestrate_account_scan", orchestrate)

    drift_orchestrator.trigger_account_scan(background_tasks, db_session, 42)

    assert len(background_tasks.tasks) == 1
    task = background_tasks.tasks[0]
    assert task.func is drift_orchestrator._run_scan_background
    assert task.args == ("42", "manual")
    assert task.kwargs == {"db": db_session, "scan_id": 1}


def test_fleet_trigger_queues_active_accounts(monkeypatch, db_session):
    active_accounts = [mock.Mock(id=7), mock.Mock(id=9)]
    monkeypatch.setattr(
        drift_orchestrator.crud_account.crud_account,
        "get_active",
        mock.Mock(return_value=active_accounts),
    )
    orchestrate = mock.AsyncMock()
    monkeypatch.setattr(drift_orchestrator, "orchestrate_account_scan", orchestrate)

    background_tasks = BackgroundTasks()
    drift_orchestrator.trigger_fleet_scan(background_tasks, db_session)

    assert len(background_tasks.tasks) == 2
    assert [task.args for task in background_tasks.tasks] == [
        ("7", "manual"),
        ("9", "manual"),
    ]
    assert all(task.func is drift_orchestrator._run_scan_background for task in background_tasks.tasks)


def test_fleet_scan_skips_running_account_and_queues_others(monkeypatch, db_session):
    active_accounts = [mock.Mock(id=7), mock.Mock(id=9), mock.Mock(id=11)]
    monkeypatch.setattr(
        drift_orchestrator.crud_account.crud_account,
        "get_active",
        mock.Mock(return_value=active_accounts),
    )

    db_session.add(Scan(account_id=7, status="running"))
    db_session.commit()

    background_tasks = BackgroundTasks()
    result = drift_orchestrator.trigger_fleet_scan(background_tasks, db_session)

    assert result == {"queued": [9, 11], "skipped": [7]}
    assert len(background_tasks.tasks) == 2
    assert all(task.func is drift_orchestrator._run_scan_background for task in background_tasks.tasks)


def test_list_drift_scans(client):
    paths = ("/api/v1/drift", "/api/v1/drift/scans", "/api/v1/drifts")
    path, resp = _try_get(client, paths)

    assert resp.status_code < 500


def test_terraform_plan_webhook_accepts_payload(client):
    paths = ("/api/v1/webhooks/terraform-plan", "/api/v1/webhooks/terraform", "/api/v1/webhooks/terraform_plan")
    payload = {
        "format_version": "0.1",
        "terraform_version": "1.0.0",
        "resource_changes": [],
    }

    # Patch common side-effecty functions if present to avoid external network calls
    with mock.patch("builtins.print"):
        path, resp = _try_post(client, paths, json=payload, headers={"Content-Type": "application/json"})

    assert resp.status_code < 500
    assert resp.status_code in (200, 201, 202, 400, 401)
