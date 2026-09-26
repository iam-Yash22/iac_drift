#!/usr/bin/env python
###############################################################
# introduce_drift.py
#
# Manually changes Terraform-managed AWS resources OUTSIDE of
# Terraform, to test DriftWatch's detection. Uses boto3 directly
# since the AWS CLI isn't installed in this environment.
#
# Run against the driftwatch-admin profile (provisioning identity).
# Fill in your real resource identifiers below before running.
#
# Usage:
#   python introduce_drift.py introduce
#   python introduce_drift.py revert
#   python introduce_drift.py introduce-s3
#   python introduce_drift.py revert-s3
#   python introduce_drift.py introduce-ec2
#   python introduce_drift.py revert-ec2
#   python introduce_drift.py introduce-sg
#   python introduce_drift.py revert-sg
###############################################################

import json
import subprocess
import sys
from pathlib import Path
import boto3

from app.core.logging_config import get_logger

PROFILE = "driftwatch-admin"
BUCKET_NAME = "b1-740122274365"                     # fill in / confirm
SG_ID = "sg-0fcd7a69b5e3ae5a9"        # e.g. sg-0123456789abcdef0
REGION = "us-east-1"
TERRAFORM_DIR = Path(__file__).resolve().parent / "terraform"

session = boto3.Session(profile_name=PROFILE)
s3 = session.client("s3", region_name=REGION)
ec2 = session.client("ec2", region_name=REGION)
logger = get_logger("introduce_drift")


def introduce_s3_drift():
    print(f"Introducing drift: adding out-of-band tag to {BUCKET_NAME}")
    try:
        try:
            before = s3.get_bucket_tagging(Bucket=BUCKET_NAME)
        except s3.exceptions.ClientError as exc:
            logger.error("S3 tag pre-fetch failed for bucket %s", BUCKET_NAME, exc_info=True)
            if exc.response.get("Error", {}).get("Code") != "NoSuchTagSet":
                raise
            before = {"TagSet": []}
        logger.info("tags before: %s", before.get("TagSet", []))
        tag_set = [{"Key": "drift-test", "Value": "manual-change"}]
        logger.info("called put_bucket_tagging(Bucket=%s, Tagging=%s)", BUCKET_NAME, {"TagSet": tag_set})
        s3.put_bucket_tagging(Bucket=BUCKET_NAME, Tagging={"TagSet": tag_set})
        after = s3.get_bucket_tagging(Bucket=BUCKET_NAME)
        logger.info("tags after (re-fetched): %s", after.get("TagSet", []))
        print("Confirmed tags:", after["TagSet"])
    except Exception:
        logger.error("S3 tag introduction failed for bucket %s", BUCKET_NAME, exc_info=True)
        raise


def revert_s3_drift():
    print(f"Reverting drift: restoring Terraform tags on {BUCKET_NAME}")
    try:
        try:
            before = s3.get_bucket_tagging(Bucket=BUCKET_NAME)
        except s3.exceptions.ClientError as exc:
            logger.error("S3 tag pre-fetch failed for bucket %s", BUCKET_NAME, exc_info=True)
            if exc.response.get("Error", {}).get("Code") != "NoSuchTagSet":
                raise
            before = {"TagSet": []}
        logger.info("tags before: %s", before.get("TagSet", []))
        tag_set = [
            {"Key": "Application", "Value": "IaC DriftWatch"},
            {"Key": "ManagedBy", "Value": "Terraform"},
            {"Key": "Name", "Value": BUCKET_NAME},
        ]
        logger.info("called put_bucket_tagging(Bucket=%s, Tagging=%s)", BUCKET_NAME, {"TagSet": tag_set})
        s3.put_bucket_tagging(Bucket=BUCKET_NAME, Tagging={"TagSet": tag_set})
        after = s3.get_bucket_tagging(Bucket=BUCKET_NAME)
        logger.info("tags after (re-fetched): %s", after.get("TagSet", []))
        print("Restored tags:", after["TagSet"])
    except Exception:
        logger.error("S3 tag revert failed for bucket %s", BUCKET_NAME, exc_info=True)
        raise


def _load_ec2_baseline():
    documents = []
    state_path = TERRAFORM_DIR / "terraform.tfstate"
    try:
        documents.append(json.loads(state_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        pass

    def find_instance():
        for document in documents:
            resources = list(document.get("resources", []))
            resources.extend(document.get("values", {}).get("root_module", {}).get("resources", []))
            for resource in resources:
                if resource.get("mode") != "managed" or resource.get("type") != "aws_instance":
                    continue
                instances = resource.get("instances") or []
                attributes = instances[0].get("attributes", {}) if instances else resource.get("values", {})
                instance_id = attributes.get("id")
                tags = attributes.get("tags") or attributes.get("tags_all") or {}
                if instance_id and tags:
                    return instance_id, [{"Key": key, "Value": value} for key, value in tags.items()]
        return None

    baseline = find_instance()
    if baseline:
        return baseline

    try:
        completed = subprocess.run(
            ["terraform", "show", "-json"],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        documents.append(json.loads(completed.stdout))
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise RuntimeError("Unable to read Terraform state for the EC2 baseline") from exc

    baseline = find_instance()
    if baseline:
        return baseline

    raise RuntimeError("No managed aws_instance baseline found in Terraform state")

def introduce_ec2_drift():
    instance_id, _ = _load_ec2_baseline()
    print(f"Introducing drift: adding out-of-band tag to {instance_id}")
    ec2.create_tags(
        Resources=[instance_id],
        Tags=[{"Key": "drift-test", "Value": "manual-change"}],
    )
    print("Drift tag added.")


def revert_ec2_drift():
    instance_id, expected_tags = _load_ec2_baseline()
    print(f"Reverting drift: restoring Terraform tags on {instance_id}")
    current = ec2.describe_tags(Filters=[{"Name": "resource-id", "Values": [instance_id]}])
    current_keys = [tag["Key"] for tag in current.get("Tags", []) if "Key" in tag]
    if current_keys:
        ec2.delete_tags(Resources=[instance_id], Tags=[{"Key": key} for key in current_keys])
    ec2.create_tags(Resources=[instance_id], Tags=expected_tags)
    after = ec2.describe_tags(Filters=[{"Name": "resource-id", "Values": [instance_id]}])
    actual_tags = sorted(
        [{"Key": tag["Key"], "Value": tag["Value"]} for tag in after.get("Tags", [])],
        key=lambda tag: tag["Key"],
    )
    expected_sorted = sorted(expected_tags, key=lambda tag: tag["Key"])
    logger.info("EC2 tags after restore instance_id=%s tags=%s", instance_id, actual_tags)
    print("Restored tags:", actual_tags)
    if actual_tags != expected_sorted:
        raise RuntimeError(f"EC2 tags do not match Terraform baseline: {actual_tags}")


def introduce_sg_drift():
    print(f"Introducing drift: adding out-of-band ingress rule to {SG_ID}")
    ec2.authorize_security_group_ingress(
        GroupId=SG_ID,
        IpPermissions=[{
            "IpProtocol": "tcp",
            "FromPort": 8080,
            "ToPort": 8080,
            "IpRanges": [{"CidrIp": "203.0.113.0/24"}],
        }],
    )
    print("Ingress rule added.")


def revert_sg_drift():
    print(f"Reverting drift: removing ingress rule from {SG_ID}")
    ec2.revoke_security_group_ingress(
        GroupId=SG_ID,
        IpPermissions=[{
            "IpProtocol": "tcp",
            "FromPort": 8080,
            "ToPort": 8080,
            "IpRanges": [{"CidrIp": "203.0.113.0/24"}],
        }],
    )
    print("Ingress rule removed.")


ACTIONS = {
    "introduce": lambda: (introduce_s3_drift(), introduce_sg_drift()),
    "revert": lambda: (revert_s3_drift(), revert_sg_drift()),
    "introduce-s3": introduce_s3_drift,
    "revert-s3": revert_s3_drift,
    "introduce-ec2": introduce_ec2_drift,
    "revert-ec2": revert_ec2_drift,
    "introduce-sg": introduce_sg_drift,
    "revert-sg": revert_sg_drift,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ACTIONS:
        print(f"Usage: python {sys.argv[0]} {{{'|'.join(ACTIONS)}}}")
        sys.exit(1)
    ACTIONS[sys.argv[1]]()