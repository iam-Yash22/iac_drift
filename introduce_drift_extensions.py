import json
import sys
from pathlib import Path

import boto3


PROFILE = "driftwatch-admin"
REGION = "us-east-1"
EC2_INSTANCE_ID = "i-08b1029548fc82f67"
LAMBDA_FUNCTION_NAME = "driftwatch-test-fn"
IAM_ROLE_NAME = "driftwatch-test-lambda-exec"
TERRAFORM_DIR = Path(__file__).resolve().parent / "terraform"

session = boto3.Session(profile_name=PROFILE)
lambda_client = session.client("lambda", region_name=REGION)
iam_client = session.client("iam", region_name=REGION)
ec2_client = session.client("ec2", region_name=REGION)


def introduce_ec2_drift():
    print(f"Introducing drift: adding out-of-band tag to {EC2_INSTANCE_ID}")
    ec2_client.create_tags(
        Resources=[EC2_INSTANCE_ID],
        Tags=[{"Key": "drift-test", "Value": "manual-change"}],
    )
    print("Drift tag added.")


def revert_ec2_drift():
    print(f"Reverting drift: restoring baseline tags on {EC2_INSTANCE_ID}")
    ec2_client.delete_tags(
        Resources=[EC2_INSTANCE_ID],
        Tags=[{"Key": "drift-test"}],
    )
    print("Drift tag removed.")


def _load_lambda_baseline():
    state_path = TERRAFORM_DIR / "terraform.tfstate"
    document = json.loads(state_path.read_text(encoding="utf-8"))
    for resource in document.get("resources", []):
        if resource.get("mode") != "managed" or resource.get("type") != "aws_lambda_function":
            continue
        for instance in resource.get("instances", []):
            attributes = instance.get("attributes", {})
            if attributes.get("function_name") == LAMBDA_FUNCTION_NAME:
                tags = attributes.get("tags") or {}
                return [{"Key": key, "Value": value} for key, value in tags.items()]
    raise RuntimeError(f"No Lambda baseline found for {LAMBDA_FUNCTION_NAME}")


def introduce_lambda_drift():
    print(f"Introducing drift: adding out-of-band tag to {LAMBDA_FUNCTION_NAME}")
    lambda_client.tag_resource(
        Resource=lambda_client.get_function(FunctionName=LAMBDA_FUNCTION_NAME)["Configuration"]["FunctionArn"],
        Tags={"drift-test": "manual-change"},
    )
    print("Drift tag added.")


def revert_lambda_drift():
    print(f"Reverting drift: restoring Terraform tags on {LAMBDA_FUNCTION_NAME}")
    function_arn = lambda_client.get_function(FunctionName=LAMBDA_FUNCTION_NAME)["Configuration"]["FunctionArn"]
    current = lambda_client.list_tags(Resource=function_arn).get("Tags", {})
    baseline = _load_lambda_baseline()
    remove_keys = [key for key in current if key not in {tag["Key"] for tag in baseline}]
    if remove_keys:
        lambda_client.untag_resource(Resource=function_arn, TagKeys=remove_keys)
    lambda_client.tag_resource(Resource=function_arn, Tags={tag["Key"]: tag["Value"] for tag in baseline})
    after = lambda_client.list_tags(Resource=function_arn).get("Tags", {})
    print("Restored tags:", [{"Key": key, "Value": value} for key, value in sorted(after.items())])


def _load_iam_role_baseline():
    state_path = TERRAFORM_DIR / "terraform.tfstate"
    document = json.loads(state_path.read_text(encoding="utf-8"))
    for resource in document.get("resources", []):
        if resource.get("mode") != "managed" or resource.get("type") != "aws_iam_role":
            continue
        for instance in resource.get("instances", []):
            attributes = instance.get("attributes", {})
            if attributes.get("name") == IAM_ROLE_NAME:
                return attributes.get("tags") or {}
    raise RuntimeError(f"No IAM role baseline found for {IAM_ROLE_NAME}")


def introduce_iam_role_drift():
    print(f"Introducing drift: adding out-of-band tag to {IAM_ROLE_NAME}")
    iam_client.tag_role(
        RoleName=IAM_ROLE_NAME,
        Tags=[{"Key": "drift-test", "Value": "manual-change"}],
    )
    print("Drift tag added.")


def revert_iam_role_drift():
    print(f"Reverting drift: restoring Terraform tags on {IAM_ROLE_NAME}")
    current = iam_client.list_role_tags(RoleName=IAM_ROLE_NAME).get("Tags", [])
    baseline = _load_iam_role_baseline()
    baseline_keys = set(baseline)
    remove_keys = [tag["Key"] for tag in current if tag["Key"] not in baseline_keys]
    if remove_keys:
        iam_client.untag_role(RoleName=IAM_ROLE_NAME, TagKeys=remove_keys)
    iam_client.tag_role(
        RoleName=IAM_ROLE_NAME,
        Tags=[{"Key": key, "Value": value} for key, value in baseline.items()],
    )
    after = iam_client.list_role_tags(RoleName=IAM_ROLE_NAME).get("Tags", [])
    print("Restored tags:", sorted(after, key=lambda tag: tag["Key"]))


ACTIONS = {
    "introduce-ec2": introduce_ec2_drift,
    "revert-ec2": revert_ec2_drift,
    "introduce-lambda": introduce_lambda_drift,
    "revert-lambda": revert_lambda_drift,
    "introduce-iam-role": introduce_iam_role_drift,
    "revert-iam-role": revert_iam_role_drift,
}


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ACTIONS:
        print(f"Usage: python {sys.argv[0]} {{{'|'.join(ACTIONS)}}}")
        sys.exit(1)
    ACTIONS[sys.argv[1]]()