from pathlib import Path

from app.parsers.state_parser import parse_state_file


def test_sample_state_file_contains_applied_bucket_and_three_persistable_resources():
    state_path = Path("terraform_samples/terraform.tfstate")
    resources = parse_state_file(state_path)
    persistable = [resource for resource in resources if resource.get("mode") != "data"]

    assert any(
        resource.get("resource_type") == "aws_s3_bucket"
        and resource.get("attributes", {}).get("bucket") == "b1-740122274365"
        for resource in persistable
    )
    assert len(persistable) == 3