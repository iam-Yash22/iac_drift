import asyncio
import pytest
from unittest import mock
from fastapi import BackgroundTasks
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.api import deps
from app.api.v1.endpoints.accounts import trigger_account_scan
from app.models.account import AwsAccount
from app.models.scan import Scan
from app.crud.crud_account import crud_account
from app.schemas.account import AccountCreate
from moto import mock_aws


@mock_aws
def test_create_account_requires_authentication(client):
    with mock.patch("boto3.client") as mock_boto_client:
        mock_sts_client = mock.Mock()
        mock_sts_client.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "AKIAEXAMPLE",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
            }
        }
        mock_boto_client.return_value = mock_sts_client

        resp = client.post(
            "/api/v1/accounts",
            json={"account_id": "111122223333", "role_name": "OrganizationAccountAccessRole"},
        )

        assert resp.status_code == 401
        mock_boto_client.assert_not_called()


@mock_aws
def test_list_accounts_requires_authentication(client):
    with mock.patch("boto3.client") as mock_boto_client:
        mock_boto_client.return_value = mock.Mock()

        resp = client.get("/api/v1/accounts")

        assert resp.status_code == 401
        mock_boto_client.assert_not_called()


def test_account_creation_assigns_external_id(db_session):
    account = crud_account.create(
        db_session,
        obj_in=AccountCreate(
            name="Generated ID account",
            account_id="123456789012",
            role_arn="arn:aws:iam::123456789012:role/DriftWatch",
        ),
    )

    assert account.external_id
    assert len(account.external_id) == 32
    assert all(character in "0123456789abcdef" for character in account.external_id)


def test_list_accounts_backfills_missing_external_id(db_session):
    account = AwsAccount(
        account_id="123456789012",
        name="Legacy account",
        role_arn="arn:aws:iam::123456789012:role/DriftWatch",
        external_id=None,
    )
    db_session.add(account)
    db_session.commit()

    listed = crud_account.get_all(db_session)

    assert listed[0].external_id
    assert len(listed[0].external_id) == 32


def test_owner_can_queue_manual_account_scan(monkeypatch, db_session):
    account = AwsAccount(
        account_id="111122223333",
        name="Owned account",
        role_arn="arn:aws:iam::111122223333:role/DriftWatch",
        owner_id=7,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    background_tasks = BackgroundTasks()
    queue_scan = mock.Mock()
    monkeypatch.setattr(
        "app.api.v1.endpoints.accounts.drift_orchestrator.trigger_account_scan",
        queue_scan,
    )

    response = trigger_account_scan(
        account_id=account.id,
        background_tasks=background_tasks,
        current_user=mock.Mock(id=7, role="viewer"),
        db=db_session,
    )

    assert response == {"status": "accepted", "account_id": str(account.id)}
    queue_scan.assert_called_once_with(background_tasks, db_session, account.id, triggered_by_id=7)


def test_automated_scan_orchestration_integrity_error_marks_failed_and_unlocks_account(client, db_session, monkeypatch):
    user = mock.Mock(id=7, role="viewer")
    account = AwsAccount(
        account_id="222233334444",
        name="Integrity recovery account",
        role_arn="arn:aws:iam::222233334444:role/DriftWatch",
        owner_id=user.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    calls = {"count": 0}

    async def fail_then_complete(*args, db, scan_id, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            failed_scan = db.get(Scan, scan_id)
            failed_scan.status = "running"
            db.commit()
            raise IntegrityError("SELECT 1", {}, Exception("database unavailable"))
        completed_scan = db.get(Scan, scan_id)
        completed_scan.status = "completed"
        completed_scan.result = {"summary": {"total_resources": 0, "drifted_resources": 0}}
        db.commit()

    monkeypatch.setattr("app.api.v1.endpoints.accounts.drift_orchestrator.orchestrate_account_scan", fail_then_complete)
    client.app.dependency_overrides[deps.get_current_user] = lambda: user

    response = client.post(f"/api/v1/accounts/{account.id}/automated-scan")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert "database unavailable" in body["error"]
    assert db_session.query(Scan).filter(Scan.account_id == account.id, Scan.status.in_(["queued", "running"])).count() == 0

    response = client.post(f"/api/v1/accounts/{account.id}/automated-scan")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_manual_account_scan_rejects_missing_account(db_session):
    with pytest.raises(HTTPException) as error:
        trigger_account_scan(
            account_id=999,
            background_tasks=BackgroundTasks(),
            current_user=mock.Mock(id=7, role="viewer"),
            db=db_session,
        )

    assert error.value.status_code == 404


def test_manual_account_scan_rejects_duplicate_in_progress(db_session):
    account = AwsAccount(
        account_id="111122223333",
        name="Owned account",
        role_arn="arn:aws:iam::111122223333:role/DriftWatch",
        owner_id=7,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    from app.services import drift_orchestrator

    drift_orchestrator.trigger_account_scan(
        BackgroundTasks(),
        db_session,
        account.id,
        triggered_by_id=7,
    )

    with pytest.raises(ValueError, match="scan already in progress"):
        drift_orchestrator.trigger_account_scan(
            BackgroundTasks(),
            db_session,
            account.id,
            triggered_by_id=8,
        )


def test_scan_unique_index_blocks_duplicate_queued_rows(db_session):
    account = AwsAccount(
        account_id="111122223333",
        name="Conflict account",
        role_arn="arn:aws:iam::111122223333:role/DriftWatch",
        owner_id=7,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    db_session.add_all([
        Scan(account_id=account.id, status="queued"),
        Scan(account_id=account.id, status="queued"),
    ])

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_orchestrate_account_scan_marks_failed_and_unlocks_account(monkeypatch, db_session):
    account = AwsAccount(
        account_id="111122223333",
        name="Recovery account",
        role_arn="arn:aws:iam::111122223333:role/DriftWatch",
        owner_id=7,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    scan = Scan(account_id=account.id, status="running")
    db_session.add(scan)
    db_session.commit()
    db_session.refresh(scan)
    scan_id = scan.id

    from app.services import drift_orchestrator

    monkeypatch.setattr(
        drift_orchestrator,
        "_load_terraform_reference",
        mock.Mock(side_effect=RuntimeError("boom")),
    )

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(
            drift_orchestrator.orchestrate_account_scan(
                str(account.id),
                db=db_session,
                scan_id=scan_id,
            )
        )

    fresh_session = sessionmaker(bind=db_session.bind)()
    try:
        refreshed = fresh_session.query(Scan).filter(Scan.id == scan_id).one()
        assert refreshed.status == "failed"
        assert "boom" in (refreshed.error or "")

        drift_orchestrator.trigger_account_scan(
            BackgroundTasks(),
            fresh_session,
            account.id,
            triggered_by_id=7,
        )

        queued_scans = fresh_session.query(Scan).filter(Scan.account_id == account.id).all()
        assert any(item.status == "queued" for item in queued_scans)
    finally:
        fresh_session.close()


def test_orchestrate_account_scan_marks_db_error_failed_and_unlocks_account(monkeypatch, db_session):
    account = AwsAccount(
        account_id="111122223334",
        name="DB failure recovery account",
        role_arn="arn:aws:iam::111122223334:role/DriftWatch",
        owner_id=7,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    scan = Scan(account_id=account.id, status="running")
    db_session.add(scan)
    db_session.commit()
    db_session.refresh(scan)
    scan_id = scan.id

    from app.services import drift_orchestrator

    db_error = IntegrityError("SELECT 1", {}, Exception("database unavailable"))
    monkeypatch.setattr(
        drift_orchestrator,
        "_load_terraform_reference",
        mock.Mock(side_effect=db_error),
    )

    with pytest.raises(IntegrityError, match="database unavailable"):
        asyncio.run(
            drift_orchestrator.orchestrate_account_scan(
                str(account.id),
                db=db_session,
                scan_id=scan_id,
            )
        )

    fresh_session = sessionmaker(bind=db_session.bind)()
    try:
        refreshed = fresh_session.query(Scan).filter(Scan.id == scan_id).one()
        assert refreshed.status == "failed"
        assert "database unavailable" in (refreshed.error or "")
    finally:
        fresh_session.close()
