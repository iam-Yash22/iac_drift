"""
SETUP GUIDE: Enable AWS Resource Fetching for Scan Endpoint
=============================================================

The scan endpoint is fully implemented and connected to:
✓ Account database
✓ AWS client factory
✓ Resource fetchers (EC2, S3, IAM, RDS)
✓ Drift detection engine
✓ Scan status tracking

The ONLY missing piece is AWS credentials in the .env file.

This guide shows 3 ways to add credentials:

## OPTION 1: Use Real AWS Credentials (Recommended for Development)
================================================

Step 1: Create AWS IAM User or get temporary credentials
  - In AWS Console → IAM → Users → Create User
  - Or use AWS CLI: aws sts get-session-token
  - Or use AWS SSO: aws sso login --profile my-profile

Step 2: Generate access keys for the user
  - Console: Users → {UserName} → Security credentials → Create access key
  - Copy: Access Key ID and Secret Access Key

Step 3: Update .env file
  
  Open: d:\iac_driftwatch\.env
  
  Uncomment and fill in:
    CLOUD__AWS_ACCESS_KEY_ID=AKIA...
    CLOUD__AWS_SECRET_ACCESS_KEY=...
  
  Example:
    CLOUD__AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
    CLOUD__AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
    CLOUD__PROVIDER=aws

Step 4: Ensure IAM user has permission to assume the role
  - The role in account 740122274365 must allow STS AssumeRole
  - Policy: sts:AssumeRole on arn:aws:iam::740122274365:role/iac_driftwatch_role

Step 5: Restart application
  - Ctrl+C in uvicorn terminal
  - Run: python -m uvicorn main:app --reload

Step 6: Test the endpoint
  - Run: python test_scan_flow.py
  - Should show: ✓ ALL CHECKS PASSED

## OPTION 2: Use AWS CLI Credentials (Automatic from ~/.aws/credentials)
===================================================

If you already have AWS CLI configured with profiles:

Step 1: Check your AWS profile
  aws sts get-caller-identity --profile my-profile

Step 2: Get temporary credentials from your profile
  aws sts get-session-token --profile my-profile --duration-seconds 3600 --output json

Step 3: Extract credentials from the output:
  {
    "Credentials": {
      "AccessKeyId": "ASIA...",
      "SecretAccessKey": "...",
      "SessionToken": "..."
    }
  }

Step 4: Update .env with temporary credentials:
  CLOUD__AWS_ACCESS_KEY_ID=ASIA...
  CLOUD__AWS_SECRET_ACCESS_KEY=...
  CLOUD__AWS_SESSION_TOKEN=...
  CLOUD__PROVIDER=aws

Step 5: Restart application and test

## OPTION 3: Use AWS Environment Variables (Without .env)
======================================================

If you prefer not to store credentials in .env:

Option 3A: Set environment variables before starting app
  set AWS_ACCESS_KEY_ID=AKIA...
  set AWS_SECRET_ACCESS_KEY=...
  python -m uvicorn main:app --reload

Option 3B: Use AWS_PROFILE
  set AWS_PROFILE=my-profile
  python -m uvicorn main:app --reload

Option 3C: Use AWS SSO
  aws sso login --profile my-profile
  set AWS_PROFILE=my-profile
  python -m uvicorn main:app --reload

Note: boto3 will automatically load from environment/profile in this order:
  1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
  2. AWS credentials file (~/.aws/credentials)
  3. AWS config file (~/.aws/config)
  4. IAM role (if running on EC2)

## OPTION 4: Use Mock AWS (Development/Testing Only)
====================================================

To test without real AWS credentials, use moto library (already available):

Step 1: Create a test script with moto
  # See: test_scan_with_moto.py (below)

Step 2: This allows you to test the full flow without AWS credentials

## OPTION 5: Disable AWS Integration (Development Only)
=================================================

For development without AWS, modify the endpoint to skip AWS fetching:

File: app/api/v1/endpoints/accounts.py

Replace in create_scan():
  drift_orchestrator.trigger_account_scan(...)

With:
  # For development: create scan without triggering orchestrator
  # In production, uncomment the line above
  # drift_orchestrator.trigger_account_scan(background_tasks, db, account.id, scan_id=scan.id)

Then manually update scan status:
  scan.status = "completed"
  scan.result = {"message": "Mock scan - AWS integration disabled"}

## QUICK START

1. Get AWS credentials (see Option 1, Step 1-2)

2. Update .env:
   Edit: d:\iac_driftwatch\.env
   Add:
     CLOUD__AWS_ACCESS_KEY_ID=AKIA...
     CLOUD__AWS_SECRET_ACCESS_KEY=...

3. Restart app:
   Ctrl+C in uvicorn terminal
   python -m uvicorn main:app --reload

4. Test:
   python test_scan_flow.py

5. If test passes:
   curl -X POST http://127.0.0.1:8000/accounts/1/scans \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json"

6. Check results:
   curl http://127.0.0.1:8000/accounts/1/scans/scan_2 \
     -H "Authorization: Bearer <TOKEN>"
   
   Status should progress: queued → running → completed (or failed)

## TROUBLESHOOTING

Error: InvalidClientTokenId
  Cause: Base AWS credentials are invalid or expired
  Fix: 
    1. Verify credentials in .env are correct
    2. If using temporary credentials, get new ones
    3. Check credentials have not expired

Error: AccessDenied
  Cause: Base credentials don't have permission to assume role
  Fix:
    1. Verify the role exists in account 740122274365
    2. Check the role's trust policy allows your credentials
    3. Verify role name matches: iac_driftwatch_role

Error: NoCredentialsError
  Cause: No credentials found in environment, ~/.aws, or role
  Fix:
    1. Verify .env has CLOUD__AWS_ACCESS_KEY_ID set
    2. Verify not in a file that's ignored (check .gitignore)
    3. Check application restarted after .env change

Error: Region not found
  Cause: AWS_REGION not set
  Fix: Verify .env has: AWS_REGION=us-east-1

Error: Assumed role session name error
  Cause: Role assumed with invalid session name
  Fix: Usually means base credentials are wrong, see InvalidClientTokenId

## CURRENT STATUS

Database: ✓ Connected (PostgreSQL)
Scans Table: ✓ Created with all columns
Account Registered: ✓ 740122274365 (project_account)
Role ARN: ✓ arn:aws:iam::740122274365:role/iac_driftwatch_role
External ID: ✓ Stored in database
Cloud Provider: ✓ Set to "aws" in config
Endpoint: ✓ Fully implemented
Orchestrator: ✓ Ready to fetch resources
Resource Fetchers: ✓ Implemented (EC2, S3, IAM, RDS, Security Groups)
Drift Engine: ✓ Implemented
Scan Status Tracking: ✓ Implemented

AWS Credentials: ✗ MISSING (NEEDS ACTION)

## NEXT STEP

Choose an option above and add credentials to .env, then restart the application!
"""
