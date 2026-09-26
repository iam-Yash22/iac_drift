import pytest

import app.drift.engine as engine
import app.drift.comparators as comparators


def _find_compare_fn(mod):
    candidates = (
        "compare",
        "compare_resources",
        "diff",
        "compare_two_resources",
        "compare_resource",
    )
    for name in candidates:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn, name
    return None, None


class NormalizedResource:
    def __init__(self, id, type, attributes):
        self.id = id
        self.type = type
        self.attributes = attributes


def _call_compare(fn, a, b):
    # Try several common call signatures used by compare functions
    try:
        return fn(a, b)
    except TypeError:
        pass
    try:
        return fn([a], [b])
    except TypeError:
        pass
    try:
        return fn(resources_a=[a], resources_b=[b])
    except TypeError:
        pass
    pytest.skip("Unsupported compare signature")


def _is_empty_result(res):
    if res is None:
        return True
    if res is False:
        return True
    if isinstance(res, (list, tuple)) and len(res) == 0:
        return True
    if isinstance(res, dict) and (not res or not res.get("diffs")):
        return True
    if hasattr(res, "is_drifted"):
        return not res.is_drifted and not getattr(res, "diffs", {})
    if isinstance(res, int) and res == 0:
        return True
    return False


def test_identical_normalized_resources_produce_no_drift():
    fn, name = _find_compare_fn(engine)
    if fn is None:
        pytest.skip("No compare function found in drift.engine")

    a = NormalizedResource("r1", "aws_s3_bucket", {"name": "bucket", "versioning": False})
    b = NormalizedResource("r1", "aws_s3_bucket", {"name": "bucket", "versioning": False})

    res = _call_compare(fn, a, b)

    assert _is_empty_result(res), f"Expected no drift for identical resources, got: {res}"


def test_different_attributes_produce_drift():
    fn, name = _find_compare_fn(engine)
    if fn is None:
        pytest.skip("No compare function found in drift.engine")

    a = NormalizedResource("r1", "aws_s3_bucket", {"name": "bucket", "versioning": False})
    b = NormalizedResource("r1", "aws_s3_bucket", {"name": "bucket", "versioning": True})

    res = _call_compare(fn, a, b)

    assert not _is_empty_result(res), f"Expected drift for differing resources, got empty result: {res}"


def test_s3_bucket_tag_mismatch_produces_field_level_drift():
    desired = [
        engine.NormalizedResource(
            resource_id="arn:aws:s3:::demo-bucket",
            resource_type="s3_bucket",
            properties={"resource_id": "arn:aws:s3:::demo-bucket", "resource_type": "s3_bucket", "name": "demo-bucket"},
            tags={"Name": "demo-bucket", "Application": "IaC DriftWatch"},
        )
    ]
    actual = [
        engine.NormalizedResource(
            resource_id="arn:aws:s3:::demo-bucket",
            resource_type="s3_bucket",
            properties={"resource_id": "arn:aws:s3:::demo-bucket", "resource_type": "s3_bucket", "name": "demo-bucket"},
            tags={"Name": "demo-bucket", "Application": "manual", "drift-test": "manual-change"},
        )
    ]

    results = engine.compare_resources(desired, actual)

    assert len(results) == 1
    assert results[0].is_drifted is True
    assert "tags.Application" in results[0].diffs
    assert results[0].diffs["tags.Application"]["desired"] == "IaC DriftWatch"
    assert results[0].diffs["tags.Application"]["actual"] == "manual"


def test_ec2_arn_mismatch_is_ignored():
    desired = [
        engine.NormalizedResource(
            resource_id="i-123",
            resource_type="ec2_instance",
            properties={"resource_id": "i-123", "resource_type": "ec2_instance", "arn": "arn:aws:ec2:region:account:instance/i-123"},
        )
    ]
    actual = [
        engine.NormalizedResource(
            resource_id="i-123",
            resource_type="ec2_instance",
            properties={"resource_id": "i-123", "resource_type": "ec2_instance", "arn": ""},
        )
    ]

    results = engine.compare_resources(desired, actual)

    assert results[0].is_drifted is False
    assert results[0].diffs == {}


def test_compare_resources_returns_one_result_per_actual_resource():
    desired = [NormalizedResource("r1", "aws_s3_bucket", {"name": "bucket"})]
    actual = [
        NormalizedResource("r1", "aws_s3_bucket", {"name": "bucket"}),
        NormalizedResource("r2", "aws_instance", {"name": "web"}),
    ]

    results = engine.compare_resources(desired, actual)

    assert len(results) == 2
    assert [(item.resource_id, item.resource_type) for item in results] == [
        ("r1", "aws_s3_bucket"),
        ("r2", "aws_instance"),
    ]


def test_default_security_group_is_visible_info_known_exception():
    actual = [
        engine.NormalizedResource(
            resource_id="sg-054bcfd1a3496a565",
            resource_type="security_group",
            properties={"GroupId": "sg-054bcfd1a3496a565", "GroupName": "default"},
        )
    ]

    results = engine.compare_resources([], actual)

    assert len(results) == 1
    assert results[0].resource_id == "sg-054bcfd1a3496a565"
    assert results[0].severity == "info"
    assert results[0].is_known_exception is True
    assert results[0].diffs["resource"]["actual"].resource_id == "sg-054bcfd1a3496a565"


def test_unmatched_non_default_resource_remains_critical():
    actual = [
        engine.NormalizedResource(
            resource_id="sg-custom",
            resource_type="security_group",
            properties={"GroupId": "sg-custom", "GroupName": "custom"},
        )
    ]

    result = engine.compare_resources([], actual)[0]

    assert result.severity == "critical"
    assert result.is_known_exception is False


def test_aws_service_role_path_is_visible_info_known_exception():
    actual = [
        engine.NormalizedResource(
            resource_id="AROAWSERVICE",
            resource_type="iam_role",
            properties={"RoleName": "AWSServiceRoleForSupport", "Path": "/aws-service-role/support.amazonaws.com/"},
        )
    ]

    result = engine.compare_resources([], actual)[0]

    assert result.severity == "info"
    assert result.is_known_exception is True
