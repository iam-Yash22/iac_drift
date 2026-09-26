import os

from core.config import settings
from db.session import SessionLocal


def _abort_if_production():
    env = getattr(settings, "ENV", None) or os.getenv("ENV", "").lower()
    if env in {"production", "prod"}:
        raise RuntimeError("seed_demo_data.py cannot run in production environments")


def seed_demo_data():
    _abort_if_production()

    with SessionLocal() as session:
        from crud.account import create_account
        from crud.resource import create_resource
        from crud.drift import create_drift_record
        from schemas.account import AccountCreate
        from schemas.resource import ResourceCreate
        from schemas.drift import DriftRecordCreate

        account_data = [
            {"name": "Acme Corp", "email": "ops@acme.example"},
            {"name": "Northwind", "email": "platform@northwind.example"},
        ]

        created_accounts = []
        for item in account_data:
            created_accounts.append(
                create_account(session, AccountCreate(**item))
            )

        for index, account in enumerate(created_accounts, start=1):
            resource = create_resource(
                session,
                ResourceCreate(
                    account_id=account.id,
                    name=f"prod-stack-{index}",
                    type="aws_ecs",
                    region="us-east-1",
                ),
            )

            create_drift_record(
                session,
                DriftRecordCreate(
                    account_id=account.id,
                    resource_id=resource.id,
                    drift_type="configuration",
                    summary=f"Demo drift for {resource.name}",
                    details="Representative drift record for demo purposes.",
                    severity="medium",
                ),
            )

        session.commit()


if __name__ == "__main__":
    seed_demo_data()
    print("Demo data seeded successfully")
