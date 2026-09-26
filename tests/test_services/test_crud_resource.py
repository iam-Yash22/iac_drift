from app.crud.crud_resource import crud_resource
from app.models.resource import TrackedResource
from app.parsers.normalizer import NormalizedResource


def test_upsert_normalized_resource_stores_resource_name_in_configuration(db_session):
    resource = NormalizedResource(
        resource_type="aws_instance",
        resource_name="web",
        resource_id="i-123",
        region="us-east-1",
        attributes={"instance_type": "t3.micro"},
    )

    record = crud_resource.upsert_snapshot(
        db_session,
        snapshot={**resource.__dict__, "account_id": 1},
    )

    assert isinstance(record, TrackedResource)
    assert record.configuration["resource_name"] == "web"
    assert record.configuration["instance_type"] == "t3.micro"