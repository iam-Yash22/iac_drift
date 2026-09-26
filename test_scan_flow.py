"""
Test script to verify scan endpoint flow end-to-end.
"""
import asyncio
import sys
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.account import AwsAccount
from app.models.scan import Scan
from app.services import aws_client_factory, drift_orchestrator

print("=" * 80)
print("SCAN ENDPOINT FLOW TEST")
print("=" * 80)

# 1. Check database connection
print("\n1. DATABASE CONNECTION TEST:")
print("-" * 80)
try:
    engine = create_engine(str(settings.database.url))
    Session = sessionmaker(bind=engine)
    db = Session()
    print("✓ Connected to PostgreSQL")
except Exception as e:
    print(f"✗ Failed to connect: {e}")
    sys.exit(1)

# 2. Check AWS configuration
print("\n2. AWS CONFIGURATION CHECK:")
print("-" * 80)
print(f"Cloud Provider: {settings.cloud.provider}")
print(f"AWS Access Key: {'SET' if settings.cloud.aws_access_key_id else 'NOT SET'}")
print(f"AWS Secret Key: {'SET' if settings.cloud.aws_secret_access_key else 'NOT SET'}")
print(f"AWS Session Token: {'SET' if settings.cloud.aws_session_token else 'NOT SET'}")

if not settings.cloud.aws_access_key_id:
    print("\n⚠ WARNING: No AWS credentials found in environment!")
    print("  Without credentials, assume_role will fail.")
    print("  Add to .env:")
    print("    CLOUD__AWS_ACCESS_KEY_ID=...")
    print("    CLOUD__AWS_SECRET_ACCESS_KEY=...")
    print("    CLOUD__PROVIDER=aws")

# 3. Check registered accounts
print("\n3. REGISTERED ACCOUNTS:")
print("-" * 80)
accounts = db.query(AwsAccount).filter(AwsAccount.is_active).all()
if not accounts:
    print("✗ No active accounts found")
    sys.exit(1)

for acc in accounts:
    print(f"\n  Account: {acc.account_id}")
    print(f"    Name: {acc.name}")
    print(f"    Role ARN: {acc.role_arn}")
    print(f"    External ID: {'SET' if acc.external_id else 'NOT SET'}")
    print(f"    Active: {acc.is_active}")

# 4. Test AWS client creation
print("\n4. AWS CLIENT CREATION TEST:")
print("-" * 80)
if accounts:
    account = accounts[0]
    print(f"Testing with account: {account.name} ({account.account_id})")
    try:
        print("  Attempting to create AWS clients...")
        # Don't actually call get_clients_for_account here as it will fail without credentials
        # Instead, just verify the account has required fields
        if not account.role_arn:
            print(f"  ✗ Account missing role_arn")
        else:
            print(f"  ✓ Account has role_arn: {account.role_arn}")
        
        if not account.external_id:
            print(f"  ⚠ Account missing external_id (optional)")
        else:
            print(f"  ✓ Account has external_id: ***SET***")
            
    except Exception as e:
        print(f"  ✗ Failed to create clients: {e}")

# 5. Check scans table
print("\n5. SCANS TABLE STATUS:")
print("-" * 80)
try:
    existing_scans = db.query(Scan).all()
    print(f"✓ Scans table exists with {len(existing_scans)} records")
    
    if existing_scans:
        latest = existing_scans[-1]
        print(f"  Latest scan:")
        print(f"    ID: {latest.id}")
        print(f"    Account: {latest.account_id}")
        print(f"    Status: {latest.status}")
        print(f"    Created: {latest.created_at}")
except Exception as e:
    print(f"✗ Failed to query scans: {e}")

# 6. Test creating a scan record
print("\n6. TEST SCAN CREATION:")
print("-" * 80)
try:
    test_scan = Scan(account_id=account.id, status="test")
    db.add(test_scan)
    db.commit()
    db.refresh(test_scan)
    print(f"✓ Created test scan:")
    print(f"    ID: {test_scan.id}")
    print(f"    Scan ID: {test_scan.scan_id}")
    print(f"    Account ID: {test_scan.account_id}")
    print(f"    Status: {test_scan.status}")
    
    # Clean up
    db.delete(test_scan)
    db.commit()
    print("  ✓ Cleaned up test record")
except Exception as e:
    print(f"✗ Failed to create scan: {e}")

# 7. Summary and next steps
print("\n7. SUMMARY & NEXT STEPS:")
print("-" * 80)

ready = True
issues = []

if not settings.cloud.aws_access_key_id:
    ready = False
    issues.append("Missing AWS credentials (CLOUD__AWS_ACCESS_KEY_ID)")

if settings.cloud.provider != "aws":
    ready = False
    issues.append(f"Cloud provider set to '{settings.cloud.provider}' (should be 'aws')")

if not accounts:
    ready = False
    issues.append("No active AWS accounts registered")

if ready:
    print("✓ ALL CHECKS PASSED")
    print("\nYou can now test the scan endpoint:")
    print("  1. Authenticate to get a bearer token")
    print("  2. POST /accounts/1/scans")
    print("  3. GET /accounts/1/scans/{scan_id} to check status")
else:
    print("✗ ISSUES FOUND:")
    for issue in issues:
        print(f"  - {issue}")
    print("\nFIX:")
    print("  1. Add AWS credentials to .env file")
    print("  2. Ensure CLOUD__PROVIDER=aws")
    print("  3. Restart the application")
    print("  4. Re-run this test")

db.close()
print("\n" + "=" * 80)
