"""Diagnostic script to verify AWS credentials and assume role setup."""
import os
import sys
import boto3
import botocore.exceptions

from app.core.config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.account import AwsAccount

print("=" * 80)
print("AWS CREDENTIALS & ASSUME ROLE DIAGNOSTIC")
print("=" * 80)

# 1. Check credentials are loaded
print("\n1. CREDENTIALS LOADED FROM .env")
print("-" * 80)
print(f"CLOUD__PROVIDER: {settings.cloud.provider}")
print(f"CLOUD__AWS_ACCESS_KEY_ID: {'SET' if settings.cloud.aws_access_key_id else 'NOT SET'}")
print(f"CLOUD__AWS_SECRET_ACCESS_KEY: {'SET' if settings.cloud.aws_secret_access_key else 'NOT SET'}")
print(f"CLOUD__AWS_SESSION_TOKEN: {'SET' if settings.cloud.aws_session_token else 'NOT SET'}")

if not settings.cloud.aws_access_key_id:
    print("\n✗ PROBLEM: AWS Access Key ID not set in config")
    sys.exit(1)

if not settings.cloud.aws_secret_access_key:
    print("\n✗ PROBLEM: AWS Secret Access Key not set in config")
    sys.exit(1)

# 2. Test basic AWS connectivity
print("\n2. TEST AWS CONNECTIVITY")
print("-" * 80)
try:
    # Use credentials from config (like the app does)
    access_key = settings.cloud.aws_access_key_id
    secret_key = settings.cloud.aws_secret_access_key
    session_token = settings.cloud.aws_session_token
    
    if access_key:
        access_key = access_key.get_secret_value()
    if secret_key:
        secret_key = secret_key.get_secret_value()
    if session_token:
        session_token = session_token.get_secret_value()
    
    sts = boto3.client(
        "sts",
        region_name="us-east-1",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token,
    )
    identity = sts.get_caller_identity()
    print(f"✓ Successfully connected to AWS")
    print(f"  Account ID: {identity['Account']}")
    print(f"  ARN: {identity['Arn']}")
    print(f"  User ID: {identity['UserId']}")
except Exception as e:
    print(f"✗ Failed to connect to AWS: {e}")
    print("\nThis means:")
    print("  - AWS credentials in .env are INVALID or EXPIRED")
    print("  - OR the AWS access key has been deleted")
    print("  - OR network access to AWS is blocked")
    sys.exit(1)

# 3. Check account in database
print("\n3. CHECK ACCOUNT IN DATABASE")
print("-" * 80)
try:
    engine = create_engine(str(settings.database.url))
    Session = sessionmaker(bind=engine)
    db = Session()
    
    accounts = db.query(AwsAccount).all()
    if not accounts:
        print("✗ No accounts found in database")
        sys.exit(1)
    
    for acc in accounts:
        print(f"\nAccount: {acc.name} (ID: {acc.account_id})")
        print(f"  Role ARN: {acc.role_arn}")
        print(f"  External ID: {'SET' if acc.external_id else 'NOT SET'}")
        print(f"  Active: {acc.is_active}")
        
        if not acc.role_arn:
            print(f"  ✗ ERROR: role_arn is empty!")
            continue
        
        if not acc.is_active:
            print(f"  ✗ ERROR: Account is not active!")
            continue
        
        # 4. Test assume role
        print(f"\n4. TEST ASSUME ROLE")
        print("-" * 80)
        print(f"Testing: {acc.role_arn}")
        
        try:
            response = sts.assume_role(
                RoleArn=acc.role_arn,
                RoleSessionName="driftwatch-test",
                ExternalId=acc.external_id or None
            )
            print(f"✓ Successfully assumed role!")
            print(f"  Session Token: {response['Credentials']['SessionToken'][:20]}...")
            print(f"  Expiration: {response['Credentials']['Expiration']}")
            
            # Try to use the assumed role credentials
            assumed_sts = boto3.client(
                "sts",
                aws_access_key_id=response['Credentials']['AccessKeyId'],
                aws_secret_access_key=response['Credentials']['SecretAccessKey'],
                aws_session_token=response['Credentials']['SessionToken'],
                region_name="us-east-1"
            )
            assumed_identity = assumed_sts.get_caller_identity()
            print(f"\n✓ Successfully used assumed role credentials!")
            print(f"  Assumed Account: {assumed_identity['Account']}")
            print(f"  Assumed ARN: {assumed_identity['Arn']}")
            
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            print(f"✗ Failed to assume role: {error_code}")
            print(f"  Message: {error_msg}")
            
            print(f"\nDIAGNOSIS:")
            if error_code == "InvalidClientTokenId":
                print("  Root cause: Base AWS credentials are INVALID or EXPIRED")
                print("  Solution: Generate NEW AWS credentials and update .env")
            elif error_code == "AccessDenied":
                print("  Root cause: Base AWS credentials don't have permission to assume this role")
                print("  Solution: Check role trust policy allows your principal")
            elif error_code == "NoSuchEntity":
                print("  Root cause: Role does not exist in account " + acc.account_id)
                print("  Solution: Create the role or verify the role ARN")
            elif error_code == "MalformedPolicyDocument":
                print("  Root cause: External ID format is invalid")
                print("  Solution: Check external ID value in database")
            else:
                print(f"  Root cause: {error_code}")
                print(f"  Solution: Check AWS documentation for '{error_code}'")
        
        except Exception as e:
            print(f"✗ Unexpected error: {type(e).__name__}: {e}")

except Exception as e:
    print(f"✗ Database error: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
