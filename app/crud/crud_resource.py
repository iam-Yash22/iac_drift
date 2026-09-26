import os

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from fastapi.encoders import jsonable_encoder

import app.models.resource
import app.models.terraform_baseline
import app.schemas.resource
import app.models as models
import app.schemas as schemas
from app.core.config import settings
from app.crud.base import CRUDBase


class CRUDResource(CRUDBase[models.resource.Resource, schemas.resource.ResourceCreate, schemas.resource.ResourceUpdate]):
    """Resource CRUD with upsert for snapshots and filtered listing."""

    def _normalize_payload(self, obj_data):
        if hasattr(obj_data, "dict"):
            payload = obj_data.dict()
        elif isinstance(obj_data, dict):
            payload = dict(obj_data)
        else:
            payload = dict(obj_data.__dict__)

        if "account_id" not in payload and "account" in payload and getattr(payload["account"], "id", None) is not None:
            payload["account_id"] = payload["account"].id

        if "resource_type" not in payload and "type" in payload:
            payload["resource_type"] = payload["type"]

        if "resource_id" not in payload and "id" in payload:
            payload["resource_id"] = payload["id"]

        if "name" not in payload:
            payload["name"] = (
                payload.get("resource_name")
                or payload.get("Name")
                or payload.get("RoleName")
                or payload.get("GroupName")
                or payload.get("DBInstanceIdentifier")
            )
        if "arn" not in payload:
            payload["arn"] = payload.get("Arn") or payload.get("ARN") or payload.get("BucketArn")

        if "configuration" not in payload:
            for key in ("configuration", "attributes", "properties", "data", "details"):
                if key in payload:
                    payload["configuration"] = payload[key]
                    break

        if "resource_name" in payload:
            configuration = payload.get("configuration")
            if not isinstance(configuration, dict):
                configuration = {}
            configuration.setdefault("resource_name", payload["resource_name"])
            payload["configuration"] = configuration

        if isinstance(payload.get("configuration"), dict):
            payload["configuration"] = jsonable_encoder(payload["configuration"])
        if isinstance(payload.get("tags"), dict):
            payload["tags"] = jsonable_encoder(payload["tags"])

        fixed = {k: v for k, v in payload.items() if k not in {"id", "created_at", "updated_at"}}
        return fixed

    def upsert_snapshot(self, db: Session, *, snapshot):
        obj_data = self._normalize_payload(snapshot)
        account_id = obj_data.get("account_id")
        resource_id = obj_data.get("resource_id")
        resource_type = obj_data.get("resource_type")

        if account_id is None or resource_id is None or resource_type is None:
            return None

        valid_columns = set(models.resource.Resource.__table__.columns.keys())
        filtered_data = {key: value for key, value in obj_data.items() if key in valid_columns}

        existing = (
            db.query(models.resource.Resource)
            .filter(
                models.resource.Resource.account_id == account_id,
                models.resource.Resource.resource_id == resource_id,
                models.resource.Resource.resource_type == resource_type,
            )
            .first()
        )

        if existing is not None:
            for key, value in filtered_data.items():
                setattr(existing, key, value)
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing

        record = models.resource.Resource(**filtered_data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def upsert_many(self, db: Session, *, account_id=None, resources=None):
        if not resources:
            return []

        persisted = []
        for item in resources:
            payload = self._normalize_payload(item)
            if account_id is not None:
                payload["account_id"] = int(account_id)
            if "resource_type" not in payload or "resource_id" not in payload:
                continue

            # Standardize the common live-AWS shapes used by the drift fetchers.
            if not payload.get("region"):
                payload["region"] = (
                    payload.get("Region")
                    or settings.cloud.region
                    or os.getenv("AWS_REGION")
                    or "unknown"
                )
            payload.setdefault("tags", payload.get("Tags") or payload.get("tags") or {})
            payload.setdefault("configuration", payload.get("configuration") or payload.get("attributes") or payload.get("properties") or {})

            record = self.upsert_snapshot(db, snapshot=payload)
            if record is not None:
                persisted.append(record)

        return persisted

    def create_many(self, db: Session, *, account_id=None, resources=None):
        return self.upsert_many(db, account_id=account_id, resources=resources)

    def replace_baseline(self, db: Session, *, account_id: int, resources):
        """Replace all stored baseline rows for one account atomically."""
        existing = (
            db.query(self.model)
            .filter(self.model.account_id == account_id)
            .order_by(self.model.id)
            .all()
        )
        existing_by_identity = {
            (record.resource_type, record.resource_id): record
            for record in existing
        }
        claimed_identities = set()
        persisted = []
        for resource in resources:
            payload = self._normalize_payload(resource)
            payload["account_id"] = account_id
            payload.setdefault("region", settings.cloud.region or os.getenv("AWS_REGION") or "unknown")
            payload.setdefault("tags", {})
            payload.setdefault("configuration", payload.get("attributes") or {})
            values = {
                key: value
                for key, value in payload.items()
                if key in set(self.model.__table__.columns.keys())
                and key not in {"id", "created_at", "updated_at"}
            }
            identity = (values.get("resource_type"), values.get("resource_id"))
            record = existing_by_identity.get(identity)
            if record is None:
                record = self.model(**values)
                db.add(record)
            else:
                for key, value in values.items():
                    setattr(record, key, value)
            claimed_identities.add(identity)
            persisted.append(record)

        # Keep historical drift rows valid; only remove stale resources with no history.
        for record in existing:
            if (record.resource_type, record.resource_id) not in claimed_identities and not record.drift_records:
                db.delete(record)
        db.commit()
        for record in persisted:
            db.refresh(record)
        return persisted

    def replace_terraform_baseline(self, db: Session, *, account_id: int, resources):
        """Replace one account's Terraform baseline by stable resource identity."""
        model = app.models.terraform_baseline.TerraformBaseline
        existing = (
            db.query(model)
            .filter(model.account_id == account_id)
            .order_by(model.id)
            .all()
        )
        existing_by_identity = {
            (record.resource_type, record.resource_id): record
            for record in existing
        }
        claimed_identities = set()
        persisted = []
        valid_columns = set(model.__table__.columns.keys())
        for resource in resources:
            payload = self._normalize_payload(resource)
            payload["account_id"] = account_id
            payload.setdefault("tags", {})
            payload.setdefault("configuration", payload.get("attributes") or {})
            values = {
                key: value
                for key, value in payload.items()
                if key in valid_columns and key not in {"id", "created_at", "updated_at"}
            }
            identity = (values.get("resource_type"), values.get("resource_id"))
            record = existing_by_identity.get(identity)
            if record is None:
                record = model(**values)
                db.add(record)
            else:
                for key, value in values.items():
                    setattr(record, key, value)
            claimed_identities.add(identity)
            persisted.append(record)

        for record in existing:
            if (record.resource_type, record.resource_id) not in claimed_identities:
                db.delete(record)
        db.commit()
        for record in persisted:
            db.refresh(record)
        return persisted

    def list_filtered(self, db: Session, *, account_id=None, resource_type=None, since=None, limit=100, offset=0):
        q = db.query(self.model)
        if account_id is not None:
            q = q.filter(self.model.account_id == account_id)
        if resource_type is not None:
            q = q.filter(self.model.resource_type == resource_type)
        if since is not None:
            q = q.filter(self.model.updated_at >= since)

        return q.order_by(self.model.updated_at.desc()).offset(offset).limit(limit).all()


crud_resource = CRUDResource(models.resource.Resource)
