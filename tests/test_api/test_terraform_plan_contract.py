"""Terraform-plan contract coverage using only the in-memory test fixtures."""

from types import SimpleNamespace

import pytest

from app.api import deps
from app.auth import dependencies as auth_dependencies
from app.models.account import AwsAccount
from app.models.terraform_baseline import TerraformBaseline
from app.models.user import User
@pytest.fixture
def F1():
    return {
        "resources": [
            {
                "mode": "managed",
                "type": "aws_s3_bucket",
                "name": "contract_bucket",
                "instances": [{"attributes": {"id": "contract-bucket", "bucket": "contract-bucket"}}],
            },
            {
                "mode": "managed",
                "type": "aws_instance",
                "name": "contract_instance",
                "instances": [{"attributes": {"id": "i-contract", "instance_type": "t3.micro"}}],
            },
        ]
    }


@pytest.fixture
def F2():
    return {"format_version": "1.0", "planned_values": {"root_module": {"resources": []}}}


@pytest.fixture
def F3():
    return {
        "format_version": "1.0",
        "planned_values": {
            "root_module": {
                "resources": [{"address": "aws_instance.web", "type": "aws_instance", "name": "web"}]
            }
        },
    }


@pytest.fixture
def F4():
    return {
        "values": {
            "root_module": {
                "resources": [{
                    "address": "aws_instance.web",
                    "mode": "managed",
                    "type": "aws_instance",
                    "name": "web",
                    "values": {"id": "i-contract-root", "instance_type": "t3.micro"},
                }]
            }
        }
    }


@pytest.fixture
def F5():
    return {
        "resources": [{
            "mode": "managed",
            "type": "aws_s3_bucket",
            "name": "contract_bucket",
            "instances": [{"attributes": {"id": "contract-bucket", "bucket": "contract-bucket"}}],
        }]
    }


def _account(db_session, username="terraform-contract-user"):
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password="not-used",
        role="viewer",
    )
    db_session.add(user)
    db_session.flush()
    account = AwsAccount(
        account_id="123456789012",
        name="Terraform contract account",
        role_arn="arn:aws:iam::123456789012:role/DriftWatch",
        owner_id=user.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    return user, account


def _authenticate_admin(client, user):
    current_user = SimpleNamespace(id=user.id, role="admin")
    client.app.dependency_overrides[auth_dependencies.get_current_user] = lambda: current_user
    client.app.dependency_overrides[auth_dependencies.get_current_active_user] = lambda: current_user
    client.app.dependency_overrides[deps.get_current_user] = lambda: current_user
    return current_user


def test_a1_f1_sample_state_uploads_with_parser_count(client, db_session, F1):
    user, account = _account(db_session, "terraform-contract-a1")
    _authenticate_admin(client, user)

    response = client.post(f"/api/v1/accounts/{account.id}/terraform-plan", json=F1)

    assert response.status_code == 200
    assert response.json() == {"resources_parsed": 2}
    assert db_session.query(TerraformBaseline).filter(
        TerraformBaseline.account_id == account.id
    ).count() == 2


def test_a2_f2_plan_shape_rejected(client, db_session, F2):
    user, account = _account(db_session, "terraform-contract-a2")
    _authenticate_admin(client, user)

    response = client.post(f"/api/v1/accounts/{account.id}/terraform-plan", json=F2)

    assert response.status_code == 422
    assert response.json()["message"] == "Terraform plan payload contains no resources"


def test_a3_f3_plan_shape_records_actual_error(client, db_session, F3):
    user, account = _account(db_session, "terraform-contract-a3")
    _authenticate_admin(client, user)

    response = client.post(f"/api/v1/accounts/{account.id}/terraform-plan", json=F3)

    # Actual response: status=422, code=http_error, message="Terraform plan payload contains no resources", detail=None.
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "http_error"
    assert body["message"] == "Terraform plan payload contains no resources"
    assert body["detail"] is None


def test_a4_f4_values_root_module_records_actual_result(client, db_session, F4):
    user, account = _account(db_session, "terraform-contract-a4")
    _authenticate_admin(client, user)

    response = client.post(f"/api/v1/accounts/{account.id}/terraform-plan", json=F4)

    # Actual response: status=200 with one parsed resource and no error detail.
    assert response.status_code == 200
    assert response.json() == {"resources_parsed": 1}


def test_a5_unknown_account_returns_404(client, db_session):
    user, _ = _account(db_session, "terraform-contract-a5")
    _authenticate_admin(client, user)

    response = client.post("/api/v1/accounts/999999/terraform-plan", json={"resources": []})

    assert response.status_code == 404


def test_a6_f5_prunes_ec2_baseline_row(client, db_session, F1, F5):
    user, account = _account(db_session, "terraform-contract-a6")
    _authenticate_admin(client, user)

    assert client.post(f"/api/v1/accounts/{account.id}/terraform-plan", json=F1).status_code == 200
    assert client.post(f"/api/v1/accounts/{account.id}/terraform-plan", json=F5).status_code == 200

    rows = db_session.query(TerraformBaseline).filter(TerraformBaseline.account_id == account.id).all()
    assert [(row.resource_type, row.resource_id) for row in rows] == [("s3_bucket", "contract-bucket")]


def test_a7_reupload_f1_does_not_duplicate_rows(client, db_session, F1):
    user, account = _account(db_session, "terraform-contract-a7")
    _authenticate_admin(client, user)

    assert client.post(f"/api/v1/accounts/{account.id}/terraform-plan", json=F1).status_code == 200
    assert client.post(f"/api/v1/accounts/{account.id}/terraform-plan", json=F1).status_code == 200

    assert db_session.query(TerraformBaseline).filter(TerraformBaseline.account_id == account.id).count() == 2


def test_a8_no_token_returns_401(client):
    response = client.post("/api/v1/accounts/1/terraform-plan", json={"resources": []})

    assert response.status_code == 401


def test_terraform_plan_viewer_role_is_forbidden(client, db_session):
    user, account = _account(db_session, "terraform-contract-viewer")
    current_user = SimpleNamespace(id=user.id, role="viewer")
    client.app.dependency_overrides[auth_dependencies.get_current_user] = lambda: current_user
    client.app.dependency_overrides[auth_dependencies.get_current_active_user] = lambda: current_user
    client.app.dependency_overrides[deps.get_current_user] = lambda: current_user

    response = client.post(f"/api/v1/accounts/{account.id}/terraform-plan", json={"resources": []})

    assert response.status_code == 403


def _payload_for_bytes(target_bytes: int) -> bytes:
    prefix = (
        '{"resources":[{"mode":"managed","type":"aws_s3_bucket","name":"bucket",'
        '"instances":[{"attributes":{"id":"id-string","bucket":"'
    )
    suffix = '"}}]}]}'
    payload_value = "x" * max(0, target_bytes - len(prefix.encode("utf-8")) - len(suffix.encode("utf-8")))
    return (prefix + payload_value + suffix).encode("utf-8")


def test_terraform_plan_allows_exactly_5_mib(client, db_session):
    user, account = _account(db_session, "terraform-contract-5mib")
    current_user = SimpleNamespace(id=user.id, role="operator")
    client.app.dependency_overrides[auth_dependencies.get_current_user] = lambda: current_user
    client.app.dependency_overrides[auth_dependencies.get_current_active_user] = lambda: current_user
    client.app.dependency_overrides[deps.get_current_user] = lambda: current_user

    payload = _payload_for_bytes(5 * 1024 * 1024)
    response = client.post(
        f"/api/v1/accounts/{account.id}/terraform-plan",
        content=payload,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["resources_parsed"] == 1


def test_terraform_plan_rejects_payload_over_5_mib(client, db_session):
    user, account = _account(db_session, "terraform-contract-5mib-plus-one")
    current_user = SimpleNamespace(id=user.id, role="admin")
    client.app.dependency_overrides[auth_dependencies.get_current_user] = lambda: current_user
    client.app.dependency_overrides[auth_dependencies.get_current_active_user] = lambda: current_user
    client.app.dependency_overrides[deps.get_current_user] = lambda: current_user

    payload = _payload_for_bytes(5 * 1024 * 1024 + 1)
    response = client.post(
        f"/api/v1/accounts/{account.id}/terraform-plan",
        content=payload,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413


CONTRACT_MATRIX = {
    "A1": ("F1 returns resources_parsed=2", "test_a1_f1_sample_state_uploads_with_parser_count"),
    "A2": ("F2 plan shape returns 422 no-resource", "test_a2_f2_plan_shape_rejected"),
    "A3": ("F3 plan shape records actual status/detail", "test_a3_f3_plan_shape_records_actual_error"),
    "A4": ("F4 values.root_module records actual status/detail", "test_a4_f4_values_root_module_records_actual_result"),
    "A5": ("Unknown account returns 404", "test_a5_unknown_account_returns_404"),
    "A6": ("F5 prunes EC2 baseline row", "test_a6_f5_prunes_ec2_baseline_row"),
    "A7": ("F1 twice creates no duplicate row", "test_a7_reupload_f1_does_not_duplicate_rows"),
    "A8": ("No token returns 401", "test_a8_no_token_returns_401"),
}
