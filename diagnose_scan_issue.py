"""Diagnostic report for scan endpoint AWS credentials issue."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.account import AwsAccount

print("=" * 80)
print("SCAN ENDPOINT DIAGNOSTIC REPORT")
print("=" * 80)

# 1. Check .env AWS credentials
print("\n1. ENVIRONMENT AWS CREDENTIALS:")
print("-" * 80)
cred_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 
             'CLOUD__AWS_ACCESS_KEY_ID', 'CLOUD__AWS_SECRET_ACCESS_KEY']
found_any = False
for var in cred_vars:
    val = os.getenv(var)
    if val:
        print(f"   ✓ {var}: {val[:20]}..." if len(str(val)) > 20 else f"   ✓ {var}: {val}")
        found_any = True
if not found_any:
    print("   ✗ NO AWS CREDENTIALS FOUND IN ENVIRONMENT")
    print("     The .env file is missing AWS credentials!")

# 2. Check configured AWS region
print("\n2. AWS REGION CONFIGURATION:")
print("-" * 80)
region = os.getenv('AWS_REGION') or settings.cloud.region
print(f"   Region: {region or 'NOT SET'}")

# 3. Check cloud provider
print("\n3. CLOUD PROVIDER SETTINGS:")
print("-" * 80)
print(f"   Provider: {settings.cloud.provider}")
if settings.cloud.provider == "none":
    print("   ⚠ WARNING: Cloud provider is set to 'none'")

# 4. Database AWS accounts
print("\n4. CONFIGURED AWS ACCOUNTS IN DATABASE:")
print("-" * 80)
engine = create_engine(str(settings.database.url))
Session = sessionmaker(bind=engine)
db = Session()
accounts = db.query(AwsAccount).all()

if not accounts:
    print("   ✗ NO ACCOUNTS CONFIGURED")
else:
    for acc in accounts:
        print(f"   Account: {acc.account_id} ({acc.name})")
        print(f"     Role ARN: {acc.role_arn}")
        print(f"     External ID: {'***SET***' if acc.external_id else 'NOT SET'}")
        print(f"     Active: {acc.is_active}")
        print()

# 5. Root cause
print("5. ROOT CAUSE ANALYSIS:")
print("-" * 80)
if not found_any and accounts:
    print("   ✓ AWS accounts are configured in the database")
    print("   ✗ But NO base AWS credentials are set in the .env file")
    print()
    print("   When you call a scan endpoint:")
    print("   1. The app tries to assume the account's role ARN")
    print("   2. But boto3 has no credentials to use for STS AssumeRole")
    print("   3. Result: InvalidClientTokenId error")

print()
print("6. SOLUTIONS:")
print("-" * 80)
print("""
OPTION A: Use Real AWS Credentials (Production-like)
  1. Create AWS IAM user or use temporary credentials
  2. Add to .env file:
     CLOUD__AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
     CLOUD__AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
     CLOUD__PROVIDER=aws
  3. Ensure the credentials have permission to assume the role:
     arn:aws:iam::740122274365:role/iac_driftwatch_role

OPTION B: Use Mock AWS (Moto) for Development Testing
  1. Update .env:
     CLOUD__PROVIDER=aws
     AWS_REGION=us-east-1
  2. Modify drift_orchestrator.py to use moto mock for testing
  3. Create mock accounts and resources using moto

OPTION C: Skip AWS Integration for Now
  1. Comment out the AWS scan trigger in the endpoint
  2. Return a mock successful scan response
  3. Complete other development first

RECOMMENDED: Option A
  - Get temporary AWS credentials from your AWS account
  - Add them to .env
  - Verify the role ARN exists in account 740122274365
  - Test the endpoint
""")

db.close()
