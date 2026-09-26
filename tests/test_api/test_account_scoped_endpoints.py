from types import SimpleNamespace
from unittest import mock

import pytest

from app.api import deps
from app.auth import dependencies as auth_dependencies
from app.models.account import AwsAccount
from app.models.alert import Alert
from app.models.drift import DriftRecord
from app.models.resource import Resource
from app.models.scan import Scan
from app.models.user import User
from app.models.terraform_baseline import TerraformBaseline
from app.services import drift_orchestrator
from app.utils.exceptions import ValidationError


def test_account_scoped_endpoint_reads_use_owned_account(client, db_session):
    first_user = User(
        username="first-user",
        email="first@example.com",
        hashed_password="not-used",
        role="viewer",
    )
    second_user = User(
        username="second-user",
        email="second@example.com",
        hashed_password="not-used",
        role="viewer",
    )
    db_session.add_all([first_user, second_user])
    db_session.flush()

    first_account = AwsAccount(
        account_id="111122223333",
        name="First account",
        role_arn="arn:aws:iam::111122223333:role/DriftWatch",
        owner_id=first_user.id,
        is_active=True,
    )
    second_account = AwsAccount(
        account_id="444455556666",
        name="Second account",
        role_arn="arn:aws:iam::444455556666:role/DriftWatch",
        owner_id=second_user.id,
        is_active=True,
    )
    db_session.add_all([first_account, second_account])
    db_session.flush()
    db_session.add_all([
        Resource(
            account_id=first_account.id,
            resource_id="first-resource",
            resource_type="ec2_instance",
            region="us-east-1",
            tags={},
            configuration={},
        ),
        Resource(
            account_id=second_account.id,
            resource_id="second-resource",
            resource_type="ec2_instance",
            region="us-east-1",
            tags={},
            configuration={},
        ),
    ])
    db_session.commit()

    client.app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(
        id=first_user.id,
        role="viewer",
    )

    resources = client.get("/api/v1/resources")
    assert resources.status_code == 200
    assert [item["resource_id"] for item in resources.json()] == ["first-resource"]

    for path in (
        "/api/v1/health",
        "/api/v1/health/ready",
        "/api/v1/drift",
        "/api/v1/dashboard/summary",
        "/api/v1/alerts/rules",
    ):
        response = client.get(path)
        assert response.status_code < 500, (path, response.text)

    report = client.post(
        "/api/v1/reports",
        json={"report_type": "drift", "format": "json", "account_id": first_account.id},
    )
    assert report.status_code < 500, report.text


def test_account_alerts_exclude_null_scan_rows(client, db_session):
    user = User(
        username="alert-user",
        email="alert-user@example.com",
        hashed_password="not-used",
        role="viewer",
    )
    db_session.add(user)
    db_session.flush()

    account = AwsAccount(
        account_id="777788889999",
        name="Alert account",
        role_arn="arn:aws:iam::777788889999:role/DriftWatch",
        owner_id=user.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.flush()

    scan = Scan(account_id=account.id, status="completed")
    db_session.add(scan)
    db_session.flush()

    tracked_resource = Resource(
        account_id=account.id,
        resource_id="res-legacy-filter",
        resource_type="ec2_instance",
        region="us-east-1",
        tags={},
        configuration={},
    )
    db_session.add(tracked_resource)
    db_session.flush()

    drift_record = DriftRecord(
        tracked_resource_id=tracked_resource.id,
        change_type="update",
        severity="high",
        diff={"region": {"old": "a", "new": "b"}},
    )
    db_session.add(drift_record)
    db_session.flush()

    valid_alert = Alert(
        account_id=account.id,
        scan_id=scan.id,
        drift_record_id=drift_record.id,
        resource_id="res-legacy-filter",
        resource_type="ec2_instance",
        severity="high",
        diffs={"region": {"old": "a", "new": "b"}},
        summary="resource drifted",
    )
    legacy_alert = Alert(
        account_id=account.id,
        scan_id=None,
        drift_record_id=drift_record.id,
        resource_id="res-legacy-filter",
        resource_type="ec2_instance",
        severity="medium",
        diffs={"region": {"old": "b", "new": "c"}},
        summary="legacy alert",
    )
    db_session.add_all([valid_alert, legacy_alert])
    db_session.commit()

    client.app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(
        id=user.id,
        role="viewer",
    )

    response = client.get(f"/api/v1/accounts/{account.id}/alerts")
    assert response.status_code == 200
    payload = response.json()
    assert [alert["id"] for alert in payload] == [valid_alert.id]


def test_account_scan_list_returns_recent_scans_for_account(client, db_session):
    user = User(
        username="scan-list-user",
        email="scan-list@example.com",
        hashed_password="not-used",
        role="viewer",
    )
    db_session.add(user)
    db_session.flush()

    account = AwsAccount(
        account_id="101010101010",
        name="Scan list account",
        role_arn="arn:aws:iam::101010101010:role/DriftWatch",
        owner_id=user.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.flush()

    older = Scan(account_id=account.id, status="completed")
    newer = Scan(account_id=account.id, status="failed")
    db_session.add_all([older, newer])
    db_session.commit()

    _authenticate_admin(client, user)

    response = client.get(f"/api/v1/accounts/{account.id}/scans")
    assert response.status_code == 200
    payload = response.json()
    assert [scan["id"] for scan in payload] == [newer.id, older.id]


def test_scan_reads_do_not_reauthorize_with_aws(client, db_session, monkeypatch):
    user = User(
        username="scan-read-user",
        email="scan-read@example.com",
        hashed_password="not-used",
        role="viewer",
    )
    db_session.add(user)
    db_session.flush()
    account = AwsAccount(
        account_id="555566667777",
        name="Read-only scan account",
        role_arn="arn:aws:iam::555566667777:role/DriftWatch",
        owner_id=user.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.flush()
    scan = Scan(
        account_id=account.id,
        status="completed",
        result={
            "summary": {"total_resources": 1, "drifted_resources": 1, "severity_breakdown": {"high": 1}},
            "drifts": [{"severity": "high", "diffs": {"region": {"desired": "a", "actual": "b"}}}],
            "scanned_at": "2026-09-02T00:00:00+00:00",
        },
    )
    db_session.add(scan)
    db_session.commit()

    client.app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(
        id=user.id,
        role="viewer",
    )
    assume_role = mock.Mock(side_effect=AssertionError("GET must not call AssumeRole"))
    monkeypatch.setattr(deps.aws_client_factory, "assume_role", assume_role)

    assert client.get(f"/api/v1/accounts/{account.id}/scans/{scan.id}").status_code == 200
    response = client.get(f"/api/v1/accounts/{account.id}/scans/{scan.id}/drift")
    assert response.status_code == 200
    assert response.json() == scan.result["drifts"]
    assume_role.assert_not_called()


def test_account_scoped_reads_allow_any_authenticated_user(client, db_session, monkeypatch):
    owner = User(
        username="account-owner",
        email="account-owner@example.com",
        hashed_password="not-used",
        role="viewer",
    )
    non_owner = User(
        username="aws-auth-user",
        email="aws-auth@example.com",
        hashed_password="not-used",
        role="viewer",
    )
    db_session.add_all([owner, non_owner])
    db_session.flush()
    account = AwsAccount(
        account_id="111122223333",
        name="Auth account",
        role_arn="arn:aws:iam::111122223333:role/DriftWatch",
        owner_id=owner.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    scan = Scan(account_id=account.id, status="completed")
    db_session.add(scan)
    db_session.commit()
    db_session.refresh(scan)

    db_session.add(
        Resource(
            account_id=account.id,
            resource_id="i-auth-check",
            resource_type="ec2_instance",
            region="us-east-1",
            tags={},
            configuration={},
        )
    )
    db_session.commit()

    client.app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(
        id=non_owner.id,
        role="viewer",
    )

    monkeypatch.setattr(
        drift_orchestrator.aws_client_factory,
        "get_clients_for_account",
        mock.AsyncMock(return_value={"ec2": None, "s3": None, "iam": None, "rds": None}),
    )
    monkeypatch.setattr(
        drift_orchestrator,
        "_load_terraform_reference",
        lambda *args: [{"resource_id": "i-auth-check", "resource_type": "ec2_instance"}],
    )

    response = client.post(f"/api/v1/accounts/{account.id}/scan")
    assert response.status_code == 202

    response = client.post(f"/api/v1/accounts/{account.id}/scans")
    assert response.status_code == 202

    response = client.get(f"/api/v1/accounts/{account.id}/scans/{scan.id}")
    assert response.status_code == 200

    response = client.get(f"/api/v1/accounts/{account.id}/scans/{scan.id}/drift")
    assert response.status_code == 200

    response = client.get(f"/api/v1/accounts/{account.id}/resources")
    assert response.status_code == 200


def _authenticate_admin(client, user):
    current_user = SimpleNamespace(id=user.id, role="admin")
    client.app.dependency_overrides[auth_dependencies.get_current_user] = lambda: current_user
    client.app.dependency_overrides[auth_dependencies.get_current_active_user] = lambda: current_user
    client.app.dependency_overrides[deps.get_current_user] = lambda: current_user
    return current_user


def test_terraform_plan_replaces_account_baseline(client, db_session):
    user = User(
        username="baseline-user",
        email="baseline@example.com",
        hashed_password="not-used",
        role="viewer",
    )
    db_session.add(user)
    db_session.flush()
    account = AwsAccount(
        account_id="777788889999",
        name="Baseline account",
        role_arn="arn:aws:iam::777788889999:role/DriftWatch",
        external_id="keep-this-external-id",
        owner_id=user.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.flush()
    db_session.add(
        Resource(
            account_id=account.id,
            resource_id="old-resource",
            resource_type="ec2_instance",
            region="us-east-1",
            tags={},
            configuration={},
        )
    )
    db_session.commit()
    _authenticate_admin(client, user)

    payload = {
        "format_version": "1.0",
        "values": {
            "root_module": {
                "resources": [
                    {
                        "address": "aws_instance.web",
                        "mode": "managed",
                        "type": "aws_instance",
                        "name": "web",
                        "values": {
                            "id": "i-new-resource",
                            "instance_type": "t3.micro",
                            "region": "us-east-1",
                            "tags": {"Name": "web"},
                        },
                    }
                ]
            }
        },
    }
    response = client.post(f"/api/v1/accounts/{account.id}/terraform-plan", json=payload)

    assert response.status_code == 200
    assert response.json() == {"resources_parsed": 1}
    assert db_session.query(Resource).filter(Resource.account_id == account.id).count() == 1
    assert db_session.query(Resource).filter(Resource.resource_id == "old-resource").one()
    baseline = db_session.query(TerraformBaseline).filter(TerraformBaseline.account_id == account.id).one()
    assert baseline.resource_id == "i-new-resource"
    db_session.refresh(account)
    assert account.external_id == "keep-this-external-id"
    assert account.role_arn == "arn:aws:iam::777788889999:role/DriftWatch"


def test_terraform_plan_rejects_empty_payload(client, db_session):
    user = User(
        username="empty-baseline-user",
        email="empty-baseline@example.com",
        hashed_password="not-used",
        role="viewer",
    )
    db_session.add(user)
    db_session.flush()
    account = AwsAccount(
        account_id="888899990000",
        name="Empty baseline account",
        role_arn="arn:aws:iam::888899990000:role/DriftWatch",
        owner_id=user.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    _authenticate_admin(client, user)

    response = client.post(f"/api/v1/accounts/{account.id}/terraform-plan", json={})

    assert response.status_code == 422


def test_terraform_baseline_loader_prefers_ingested_baseline(client, db_session, monkeypatch):
    user = User(username="loader-user", email="loader@example.com", hashed_password="not-used", role="viewer")
    db_session.add(user)
    db_session.flush()
    account = AwsAccount(
        account_id="666677778888",
        name="Loader account",
        role_arn="arn:aws:iam::666677778888:role/DriftWatch",
        owner_id=user.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.flush()
    db_session.add(TerraformBaseline(
        account_id=account.id,
        resource_type="s3_bucket",
        resource_id="arn:aws:s3:::ingested-only",
        name="ingested-only",
        region="us-east-1",
        tags={"Name": "ingested-only"},
        configuration={"bucket": "ingested-only"},
    ))
    db_session.commit()
    loaded = drift_orchestrator._load_terraform_reference(account.id, db_session)

    assert [(item.resource_type, item.resource_id) for item in loaded] == [
        ("s3_bucket", "arn:aws:s3:::ingested-only")
    ]


def test_terraform_baseline_loader_falls_back_for_single_account(db_session, monkeypatch):
    account = AwsAccount(
        account_id="555566667788",
        name="Single account",
        role_arn="arn:aws:iam::555566667788:role/DriftWatch",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    monkeypatch.setattr(
        drift_orchestrator,
        "_state_document_resources",
        mock.Mock(side_effect=[
            [{"resource_type": "ec2_instance", "resource_id": "i-local", "resource_name": "local"}],
            [],
        ]),
    )
    monkeypatch.setattr(
        drift_orchestrator.subprocess,
        "run",
        mock.Mock(return_value=SimpleNamespace(stdout="{}")),
    )

    loaded = drift_orchestrator._load_terraform_reference(account.id, db_session)

    assert [(item.resource_type, item.resource_id) for item in loaded] == [("ec2_instance", "i-local")]


def test_terraform_baseline_loader_rejects_missing_multi_account_baseline(db_session):
    accounts = [
        AwsAccount(
            account_id=f"44445555666{i}",
            name=f"Account {i}",
            role_arn=f"arn:aws:iam::44445555666{i}:role/DriftWatch",
            is_active=True,
        )
        for i in (1, 2)
    ]
    db_session.add_all(accounts)
    db_session.commit()

    with pytest.raises(ValueError, match=f"No Terraform baseline ingested for account {accounts[0].id}"):
        drift_orchestrator._load_terraform_reference(accounts[0].id, db_session)


def test_terraform_plan_matches_baseline_resources_by_identity(client, db_session):
    user = User(
        username="identity-baseline-user",
        email="identity-baseline@example.com",
        hashed_password="not-used",
        role="viewer",
    )
    db_session.add(user)
    db_session.flush()
    account = AwsAccount(
        account_id="999900001111",
        name="Identity baseline account",
        role_arn="arn:aws:iam::999900001111:role/DriftWatch",
        owner_id=user.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.flush()
    resources = [
        Resource(
            account_id=account.id,
            resource_id=resource_id,
            resource_type="s3_bucket",
            region="us-east-1",
            tags={"Name": resource_id},
            configuration={"version": "old"},
        )
        for resource_id in ("A", "B", "C")
    ]
    db_session.add_all(resources)
    db_session.flush()
    baseline_resources = [
        TerraformBaseline(
            account_id=account.id,
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
            name=resource.name,
            region=resource.region,
            tags=resource.tags,
            configuration=resource.configuration,
        )
        for resource in resources
    ]
    db_session.add_all(baseline_resources)
    db_session.flush()
    db_session.add_all([
        DriftRecord(tracked_resource_id=resources[0].id, change_type="modified", severity="high"),
        DriftRecord(tracked_resource_id=resources[1].id, change_type="modified", severity="high"),
    ])
    db_session.commit()
    original_ids = {resource.resource_id: resource.id for resource in baseline_resources}

    _authenticate_admin(client, user)
    payload = {
        "values": {
            "root_module": {
                "resources": [
                    {
                        "type": "aws_s3_bucket",
                        "name": "C",
                        "values": {
                            "id": "C",
                            "bucket": "C",
                            "region": "us-east-1",
                            "tags": {"Name": "C", "version": "changed"},
                        },
                    },
                    {
                        "type": "aws_instance",
                        "name": "D",
                        "values": {
                            "id": "D",
                            "instance_type": "t3.micro",
                            "region": "us-east-1",
                        },
                    },
                ]
            }
        }
    }

    response = client.post(f"/api/v1/accounts/{account.id}/terraform-plan", json=payload)

    assert response.status_code == 200
    rows = db_session.query(TerraformBaseline).filter(TerraformBaseline.account_id == account.id).all()
    rows_by_id = {row.resource_id: row for row in rows}
    assert set(rows_by_id) == {"C", "D"}
    assert {
        row.resource_id
        for row in db_session.query(Resource).filter(Resource.account_id == account.id).all()
    } == {"A", "B", "C"}
    assert rows_by_id["C"].id == original_ids["C"]
    assert rows_by_id["C"].tags["version"] == "changed"
    assert rows_by_id["D"].id not in original_ids.values()
    assert {(row.resource_type, row.resource_id) for row in rows} == {
        ("s3_bucket", "C"),
        ("ec2_instance", "D"),
    }


def test_manual_scan_accepts_aws_account_id_path(client, db_session, monkeypatch):
    user = User(
        username="scan-user-with-aws-id",
        email="scan-aws@example.com",
        hashed_password="not-used",
        role="viewer",
    )
    db_session.add(user)
    db_session.flush()
    account = AwsAccount(
        account_id="111122223333",
        name="Scan account by aws id",
        role_arn="arn:aws:iam::111122223333:role/DriftWatch",
        owner_id=user.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    monkeypatch.setattr(
        drift_orchestrator,
        "trigger_account_scan",
        mock.Mock(),
    )
    monkeypatch.setattr(
        deps.aws_client_factory,
        "assume_role",
        mock.Mock(return_value={"AccessKeyId": "ASIA123", "SecretAccessKey": "secret", "SessionToken": "token"}),
    )
    client.app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(
        id=user.id,
        role="viewer",
    )

    response = client.post(f"/api/v1/accounts/{account.account_id}/scan")

    assert response.status_code == 202
    assert response.json()["account_id"] == str(account.id)


def test_manual_scan_runs_background_orchestrator_and_persists_results(client, db_session, monkeypatch):
    user = User(
        username="scan-user",
        email="scan@example.com",
        hashed_password="not-used",
        role="viewer",
    )
    db_session.add(user)
    db_session.flush()
    account = AwsAccount(
        account_id="111122223333",
        name="Scan account",
        role_arn="arn:aws:iam::111122223333:role/DriftWatch",
        owner_id=user.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    monkeypatch.setattr(
        drift_orchestrator,
        "_load_terraform_reference",
        lambda *args: [{"resource_id": "live-resource", "resource_type": "ec2_instance"}],
    )
    ec2_client = mock.MagicMock()
    ec2_client.get_paginator.return_value.paginate.return_value = [{"Reservations": []}]
    monkeypatch.setattr(
        drift_orchestrator.aws_client_factory,
        "get_clients_for_account",
        mock.AsyncMock(return_value={"ec2": ec2_client, "s3": None, "iam": None, "rds": None}),
    )
    monkeypatch.setattr(
        drift_orchestrator.aws_resource_fetchers,
        "fetch_ec2_instances",
        mock.AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        drift_orchestrator.aws_resource_fetchers,
        "fetch_security_groups",
        mock.AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        drift_orchestrator.aws_parser,
        "normalize_live_resources",
        mock.AsyncMock(
            return_value=[
                {
                    "resource_id": "live-resource",
                    "resource_type": "ec2_instance",
                    "region": "us-east-1",
                    "tags": {},
                    "configuration": {"instance_type": "t3.micro"},
                }
            ]
        ),
    )
    monkeypatch.setattr(
        drift_orchestrator.drift_engine,
        "compare_resources",
        mock.AsyncMock(
            return_value={
                "drifts": [
                    {
                        "resource_id": "live-resource",
                        "change_type": "modified",
                        "severity": "high",
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        deps.aws_client_factory,
        "assume_role",
        mock.Mock(return_value={"AccessKeyId": "ASIA123", "SecretAccessKey": "secret", "SessionToken": "token"}),
    )
    publish = mock.Mock()
    monkeypatch.setattr(drift_orchestrator.events, "publish", publish)
    client.app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(
        id=user.id,
        role="viewer",
    )

    response = client.post(f"/api/v1/accounts/{account.id}/scan")

    assert response.status_code == 202
    persisted_resource = (
        db_session.query(Resource)
        .filter(Resource.account_id == account.id, Resource.resource_id == "live-resource")
        .one()
    )
    assert persisted_resource.resource_type == "ec2_instance"
    assert len(persisted_resource.drift_records) == 1
    publish.assert_called_once_with(
        "DriftDetectedEvent",
        {"account_id": account.id, "comparison": {"drifts": [{
            "resource_id": "live-resource",
            "change_type": "modified",
            "severity": "high",
        }]}},
    )


def test_automated_scan_endpoint_runs_scheduled_workflow_synchronously(client, db_session, monkeypatch):
    user = User(
        username="automated-scan-user",
        email="automated-scan@example.com",
        hashed_password="not-used",
        role="viewer",
    )
    db_session.add(user)
    db_session.flush()
    account = AwsAccount(
        account_id="111122223333",
        name="Automated scan account",
        role_arn="arn:aws:iam::111122223333:role/DriftWatch",
        owner_id=user.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    async def complete_scan(*args, db, scan_id, **kwargs):
        completed_scan = db.get(Scan, scan_id)
        completed_scan.status = "completed"
        completed_scan.result = {
            "summary": {"total_resources": 1, "drifted_resources": 1, "severity_breakdown": {"info": 1}},
            "drifts": [{
                "resource_id": "sg-054bcfd1a3496a565",
                "resource_type": "security_group",
                "is_drifted": True,
                "severity": "info",
                "is_known_exception": True,
            }],
        }
        db.commit()

    orchestrate = mock.AsyncMock(side_effect=complete_scan)
    monkeypatch.setattr(drift_orchestrator, "orchestrate_account_scan", orchestrate)
    client.app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(
        id=user.id,
        role="viewer",
    )

    response = client.post(f"/api/v1/accounts/{account.id}/automated-scan")

    assert response.status_code == 200
    scan = db_session.query(Scan).filter(Scan.account_id == account.id).one()
    assert response.json()["scan_id"] == f"scan_{scan.id}"
    assert response.json()["status"] == "completed"
    assert response.json()["result"]["summary"]["drifted_resources"] == 1
    assert response.json()["result"]["drifts"][0]["is_known_exception"] is True
    orchestrate.assert_awaited_once_with(
        str(account.id),
        "scheduled",
        db=mock.ANY,
        scan_id=scan.id,
    )


def test_automated_scan_endpoint_returns_persisted_failure(client, db_session, monkeypatch):
    user = User(
        username="automated-failure-user",
        email="automated-failure@example.com",
        hashed_password="not-used",
        role="viewer",
    )
    db_session.add(user)
    db_session.flush()
    account = AwsAccount(
        account_id="444455556666",
        name="Automated failure account",
        role_arn="arn:aws:iam::444455556666:role/DriftWatch",
        owner_id=user.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()

    async def fail_scan(*args, db, scan_id, **kwargs):
        failed_scan = db.get(Scan, scan_id)
        failed_scan.status = "failed"
        failed_scan.error = "AssumeRole failed"
        db.commit()
        raise RuntimeError("AssumeRole failed")

    monkeypatch.setattr(drift_orchestrator, "orchestrate_account_scan", fail_scan)
    client.app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(
        id=user.id,
        role="viewer",
    )

    response = client.post(f"/api/v1/accounts/{account.id}/automated-scan")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error"] == "AssumeRole failed"