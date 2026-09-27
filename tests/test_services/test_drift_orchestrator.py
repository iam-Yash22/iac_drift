import pytest
from types import SimpleNamespace
from unittest import mock

import boto3
from pydantic import SecretStr
from app.models.scan import Scan

import app.crud.crud_resource as crud_resource_module
import app.models.account as account_model
import app.services.drift_orchestrator as orchestrator
import app.services.aws_client_factory as aws_client_factory


@pytest.mark.asyncio
async def test_orchestrator_calls_crud_and_publishes_event(db_session, monkeypatch):
    mock_account = mock.Mock()
    monkeypatch.setattr(
        orchestrator.crud_account,
        "get_by_id",
        mock.AsyncMock(return_value=mock_account),
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator.aws_client_factory,
        "get_clients_for_account",
        mock.AsyncMock(return_value={"ec2": mock.Mock(), "s3": None, "iam": None, "rds": None}),
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator.aws_resource_fetchers,
        "fetch_ec2_instances",
        mock.AsyncMock(return_value=[{"id": "i-1"}]),
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator.aws_resource_fetchers,
        "fetch_security_groups",
        mock.AsyncMock(return_value=[]),
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator.aws_parser,
        "normalize_live_resources",
        mock.AsyncMock(return_value=[{"id": "r1"}]),
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator.drift_engine,
        "compare_resources",
        mock.AsyncMock(return_value=[{"resource_id": "r1", "resource_type": "ec2_instance", "is_drifted": True}]),
        raising=False,
    )

    mock_upsert = mock.AsyncMock()
    mock_create = mock.AsyncMock()
    mock_publish = mock.Mock()
    monkeypatch.setattr(orchestrator.crud_resource, "upsert_many", mock_upsert, raising=False)
    monkeypatch.setattr(orchestrator.crud_drift, "create", mock_create, raising=False)
    monkeypatch.setattr(orchestrator.events, "publish", mock_publish, raising=False)

    account = account_model.AwsAccount(
        account_id="123456789012",
        name="crud and publish account",
        role_arn="arn:aws:iam::123456789012:role/DriftWatch",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    result = await orchestrator.orchestrate_account_scan("123", db=db_session)

    mock_upsert.assert_awaited_once()
    mock_create.assert_awaited_once()
    mock_publish.assert_called_once()
    assert result == {
        "account_id": "123",
        "comparison": [{"resource_id": "r1", "resource_type": "ec2_instance", "is_drifted": True}],
    }


@pytest.mark.asyncio
async def test_orchestrator_alerts_only_on_drift_transition_and_reconciles(db_session, monkeypatch):
    account = account_model.AwsAccount(
        account_id="123456789012",
        name="Alert transition account",
        role_arn="arn:aws:iam::123456789012:role/DriftWatch",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    monkeypatch.setattr(orchestrator.crud_account, "get_by_id", mock.AsyncMock(return_value=account), raising=False)
    monkeypatch.setattr(
        orchestrator,
        "_load_terraform_reference",
        mock.Mock(return_value=[{"resource_id": "r1", "resource_type": "ec2_instance"}]),
    )
    monkeypatch.setattr(
        orchestrator.aws_client_factory,
        "get_clients_for_account",
        mock.AsyncMock(return_value={"ec2": mock.Mock(), "s3": None, "iam": None, "rds": None}),
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator.aws_resource_fetchers,
        "fetch_ec2_instances",
        mock.AsyncMock(return_value=[{"id": "r1", "resource_type": "ec2_instance"}]),
        raising=False,
    )
    monkeypatch.setattr(orchestrator.aws_resource_fetchers, "fetch_security_groups", mock.AsyncMock(return_value=[]), raising=False)
    monkeypatch.setattr(
        orchestrator.aws_parser,
        "normalize_live_resources",
        mock.AsyncMock(return_value=[{"resource_id": "r1", "resource_type": "ec2_instance"}]),
        raising=False,
    )
    comparison = [{"resource_id": "r1", "resource_type": "ec2_instance", "is_drifted": True, "diffs": {}}]
    compare = mock.AsyncMock(side_effect=[comparison, comparison, [{**comparison[0], "is_drifted": False}]])
    monkeypatch.setattr(orchestrator.drift_engine, "compare_resources", compare, raising=False)
    monkeypatch.setattr(orchestrator.events, "publish", mock.Mock(), raising=False)
    send_email = mock.AsyncMock()
    monkeypatch.setattr(orchestrator, "_send_alert_email", send_email)

    await orchestrator.orchestrate_account_scan(str(account.id), db=db_session)
    await orchestrator.orchestrate_account_scan(str(account.id), db=db_session)
    await orchestrator.orchestrate_account_scan(str(account.id), db=db_session)

    assert compare.await_count == 3
    send_email.assert_awaited_once()
    latest_record = (
        db_session.query(orchestrator.crud_drift.crud_drift.model)
        .order_by(orchestrator.crud_drift.crud_drift.model.id.desc())
        .first()
    )
    assert latest_record.reconciled is True


@pytest.mark.asyncio
async def test_orchestrator_with_no_drift_does_not_publish_event(db_session, monkeypatch):
    mock_account = mock.Mock()
    monkeypatch.setattr(
        orchestrator.crud_account,
        "get_by_id",
        mock.AsyncMock(return_value=mock_account),
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator.aws_client_factory,
        "get_clients_for_account",
        mock.AsyncMock(return_value={"ec2": None, "s3": None, "iam": None, "rds": None}),
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator.aws_parser,
        "normalize_live_resources",
        mock.AsyncMock(return_value=[]),
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator.drift_engine,
        "compare_resources",
        mock.AsyncMock(return_value=[]),
        raising=False,
    )

    mock_publish = mock.Mock()
    monkeypatch.setattr(orchestrator.crud_resource, "upsert_many", mock.AsyncMock(), raising=False)
    monkeypatch.setattr(orchestrator.crud_drift, "create", mock.AsyncMock(), raising=False)
    monkeypatch.setattr(orchestrator.events, "publish", mock_publish, raising=False)

    account = account_model.AwsAccount(
        account_id="123456789012",
        name="no drift publish account",
        role_arn="arn:aws:iam::123456789012:role/DriftWatch",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    await orchestrator.orchestrate_account_scan("123", db=db_session)

    mock_publish.assert_not_called()


@pytest.mark.asyncio
async def test_orchestrator_persists_scan_result(db_session, monkeypatch):
    account = account_model.AwsAccount(
        account_id="123456789012",
        name="Scan result account",
        role_arn="arn:aws:iam::123456789012:role/DriftWatch",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    scan = Scan(account_id=account.id, status="queued")
    db_session.add(scan)
    db_session.commit()
    db_session.refresh(scan)

    monkeypatch.setattr(
        orchestrator.crud_account,
        "get_by_id",
        mock.AsyncMock(return_value=account),
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator.aws_client_factory,
        "get_clients_for_account",
        mock.AsyncMock(return_value={"ec2": None, "s3": None, "iam": None, "rds": None}),
        raising=False,
    )
    monkeypatch.setattr(orchestrator.aws_parser, "normalize_live_resources", mock.AsyncMock(return_value=[]), raising=False)
    monkeypatch.setattr(
        orchestrator.drift_engine,
        "compare_resources",
        mock.AsyncMock(return_value=[]),
        raising=False,
    )
    monkeypatch.setattr(orchestrator.crud_resource, "upsert_many", mock.AsyncMock(), raising=False)
    monkeypatch.setattr(orchestrator.crud_drift, "create", mock.AsyncMock(), raising=False)

    await orchestrator.orchestrate_account_scan(str(account.id), db=db_session, scan_id=scan.id)

    db_session.refresh(scan)
    assert scan.status == "completed"
    assert scan.result["summary"]["total_resources"] == 0
    assert scan.result["drifts"] == []


@pytest.mark.asyncio
async def test_send_alert_email_uses_gmail_smtp(monkeypatch):
    smtp = mock.Mock()
    smtp.__enter__ = mock.Mock(return_value=smtp)
    smtp.__exit__ = mock.Mock(return_value=None)
    monkeypatch.setattr(orchestrator.smtplib, "SMTP", mock.Mock(return_value=smtp))
    monkeypatch.setattr(orchestrator.settings, "gmail_address", "alerts@example.com")
    monkeypatch.setattr(orchestrator.settings, "gmail_app_password", SecretStr("app-password"))
    monkeypatch.setenv("ALERT_TEST_RECIPIENT", "test-recipient@example.com")
    monkeypatch.setattr(orchestrator.settings, "app_base_url", "http://localhost:5173")

    await orchestrator._send_alert_email(
        1,
        "bucket-1",
        "s3_bucket",
        "high",
        {"tags.Name": {"desired": "bucket-1", "actual": None}},
        owner_name="creator",
        scan_id=42,
    )

    orchestrator.smtplib.SMTP.assert_called_once_with("smtp.gmail.com", 587, timeout=30)
    smtp.set_debuglevel.assert_called_once_with(1)
    smtp.starttls.assert_called_once_with()
    smtp.login.assert_called_once_with("alerts@example.com", "app-password")
    message = smtp.send_message.call_args.args[0]
    assert message["To"] == "test-recipient@example.com"
    assert "Account ID: 1" in message.get_content()
    assert "Hi creator, drift was detected on account 1." in message.get_content()
    assert "http://localhost:5173/accounts/1/scans/42" in message.get_content()
    assert "tags.Name" in message.get_content()


def test_assume_role_uses_standard_aws_environment_fallback(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIASTANDARD123")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "standard-secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "standard-session-token")
    monkeypatch.setattr(
        aws_client_factory.config,
        "settings",
        SimpleNamespace(
            cloud=SimpleNamespace(
                aws_access_key_id=None,
                aws_secret_access_key=None,
                aws_session_token=None,
                region="us-east-1",
            )
        ),
    )
    aws_client_factory._CREDENTIALS_CACHE.clear()

    fake_sts = mock.Mock()
    fake_sts.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "ASIAASSUMED123",
            "SecretAccessKey": "assumed-secret",
            "SessionToken": "assumed-token",
            "Expiration": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        }
    }
    fake_session = mock.Mock()
    fake_session.client.return_value = fake_sts
    fake_session_class = mock.Mock(return_value=fake_session)
    monkeypatch.setattr(boto3, "Session", fake_session_class)

    creds = aws_client_factory.assume_role("arn:aws:iam::123456789012:role/DriftWatch")

    assert creds["AccessKeyId"] == "ASIAASSUMED123"
    assert fake_session_class.call_args.kwargs["aws_access_key_id"] == "AKIASTANDARD123"
    assert fake_session_class.call_args.kwargs["aws_secret_access_key"] == "standard-secret"
    assert fake_session_class.call_args.kwargs["aws_session_token"] == "standard-session-token"
    fake_session.client.assert_called_once_with("sts")


def test_upsert_many_persists_live_resources_for_account(db_session):
    account = account_model.AwsAccount(
        account_id="123456789012",
        name="Live account",
        role_arn="arn:aws:iam::123456789012:role/DriftWatch",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    resources = [{
        "account_id": account.id,
        "resource_id": "i-abc123",
        "resource_type": "ec2_instance",
        "region": "us-east-1",
        "tags": {"env": "dev"},
        "configuration": {"instance_type": "t3.micro"},
    }]

    inserted = crud_resource_module.crud_resource.upsert_many(db_session, account_id=account.id, resources=resources)

    assert len(inserted) == 1
    assert inserted[0].account_id == account.id
    assert inserted[0].resource_id == "i-abc123"
