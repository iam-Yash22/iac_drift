from app.parsers.normalizer import normalize_collection


def test_normalize_collection_flattens_live_aws_fetcher_mapping():
    resources = normalize_collection(
        {
            "ec2_instances": [
                {
                    "resource_id": "i-123",
                    "resource_type": "ec2_instance",
                    "region": "us-east-1",
                }
            ],
            "s3_buckets": [
                {
                    "resource_id": "example-bucket",
                    "resource_type": "s3_bucket",
                    "region": "us-east-1",
                }
            ],
        }
    )

    assert len(resources) == 2
    assert {resource.resource_id for resource in resources} == {"i-123", "example-bucket"}