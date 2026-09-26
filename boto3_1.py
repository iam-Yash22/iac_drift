import boto3

session = boto3.Session(profile_name="driftwatch-admin")
ec2 = session.client("ec2", region_name="us-east-1")  # match your terraform provider's region

resp = ec2.describe_instance_types(Filters=[{"Name": "free-tier-eligible", "Values": ["true"]}])
print([t["InstanceType"] for t in resp["InstanceTypes"]])