import app.models.account as account_model
import app.models.resource as resource_model
import app.models.user as user_model
import app.services.dashboard_service as dashboard_service


def test_dashboard_service_exposes_public_contract(db_session):
    assert hasattr(dashboard_service, "list_resources")
    assert hasattr(dashboard_service, "get_summary")

    resources = dashboard_service.list_resources(db_session, page=1, per_page=20)
    assert isinstance(resources, list)

    summary = dashboard_service.get_summary(db_session)
    assert isinstance(summary, dict)
    assert "total_drift" in summary or "total_drifts" in summary


def test_dashboard_service_scopes_resources_to_current_user_account(db_session):
    owner = user_model.User(username="owner", email="owner@example.com", hashed_password="hashed", role="admin")
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    user_account = account_model.AwsAccount(
        account_id="111111111111",
        name="Primary account",
        role_arn="arn:aws:iam::111111111111:role/DriftWatch",
        is_active=True,
        owner_id=owner.id,
    )
    other_account = account_model.AwsAccount(
        account_id="222222222222",
        name="Other account",
        role_arn="arn:aws:iam::222222222222:role/Other",
        is_active=True,
    )
    db_session.add_all([user_account, other_account])
    db_session.commit()
    db_session.refresh(user_account)
    db_session.refresh(other_account)

    db_session.add_all([
        resource_model.TrackedResource(
            account_id=user_account.id,
            resource_id="i-123456",
            resource_type="aws_instance",
            region="us-east-1",
            tags={"env": "dev"},
            configuration={"instance_type": "t3.micro"},
        ),
        resource_model.TrackedResource(
            account_id=other_account.id,
            resource_id="i-999999",
            resource_type="aws_instance",
            region="us-west-2",
            tags={"env": "prod"},
            configuration={"instance_type": "m5.large"},
        ),
    ])
    db_session.commit()

    resources = dashboard_service.list_resources(db_session, current_user=owner)

    assert len(resources) == 1
    assert resources[0].account_id == user_account.id
    assert resources[0].resource_id == "i-123456"


def test_dashboard_service_accepts_aws_account_id_string(db_session):
    account = account_model.AwsAccount(
        account_id="333333333333",
        name="AWS account",
        role_arn="arn:aws:iam::333333333333:role/DriftWatch",
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    db_session.add(
        resource_model.TrackedResource(
            account_id=account.id,
            resource_id="i-abc123",
            resource_type="aws_instance",
            region="us-east-1",
            tags={"env": "dev"},
            configuration={"instance_type": "t3.micro"},
        )
    )
    db_session.commit()

    resources = dashboard_service.list_resources(db_session, account_id="333333333333")

    assert len(resources) == 1
    assert resources[0].account_id == account.id
    assert resources[0].resource_id == "i-abc123"
