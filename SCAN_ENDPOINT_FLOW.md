"""
SCAN ENDPOINT ARCHITECTURE & DATA FLOW
=======================================

This document explains how the scan endpoint is connected to fetch account details
from the database and retrieve actual AWS resources.

## 1. DATA FLOW (ALREADY CONNECTED)

Request Flow:
  User Request (POST /accounts/{account_id}/scans)
        ↓
  FastAPI Endpoint (accounts.py:create_scan)
        ↓
  Background Task Added (drift_orchestrator.trigger_account_scan)
        ↓
  Async Orchestrator (orchestrate_account_scan)
        ├─ Query: Get Account from DB by ID
        │   └─ Retrieved fields: account_id, role_arn, external_id
        │
        ├─ AWS Client Factory (get_clients_for_account)
        │   ├─ assume_role(role_arn, external_id)
        │   ├─ Get temporary AWS credentials
        │   └─ Create boto3 clients (EC2, S3, IAM, RDS)
        │
        ├─ AWS Resource Fetchers
        │   ├─ fetch_ec2_instances()
        │   ├─ fetch_s3_buckets()
        │   ├─ fetch_iam_roles()
        │   ├─ fetch_rds_instances()
        │   └─ fetch_security_groups()
        │
        ├─ Drift Engine (Compare)
        │   └─ Compare: Terraform definitions vs Live AWS
        │
        ├─ Persist Results
        │   ├─ Save resources to database
        │   ├─ Save drift records
        │   └─ Update scan.status = "completed"
        │       Update scan.result = comparison
        │
        └─ Return scan object with results

Response to Client:
  200 OK + ScanOut model
  {
    "id": 1,
    "scan_id": "scan_1",
    "account_id": 1,
    "status": "queued",  // or "running"/"completed"/"failed"
    "result": null,      // populated after background task completes
    "error": null,
    "created_at": "...",
    "updated_at": "..."
  }

## 2. DATABASE CONNECTIONS

Account Model (app/models/account.py):
  - account_id: String (e.g., "740122274365")
  - name: String (e.g., "project_account")
  - role_arn: String (e.g., "arn:aws:iam::740122274365:role/iac_driftwatch_role")
  - external_id: String (encrypted, used for cross-account access)
  - is_active: Boolean
  
  ↓ Fetched by CRUD

Scan Model (app/models/scan.py):
  - id: Integer (Primary Key)
  - account_id: Integer (Foreign Key → aws_accounts.id)
  - status: String ("queued", "running", "completed", "failed")
  - result: JSON (comparison results)
  - error: String (error message if failed)
  - created_at: DateTime
  - updated_at: DateTime

## 3. KEY FUNCTIONS & FLOW

a) Endpoint: GET /accounts/{account_id}/scans/{scan_id}
   └─ Handler: get_scan()
      └─ Retrieves Scan by ID and account_id
      └─ Returns current status and results

b) Orchestrator: orchestrate_account_scan()
   ├─ Gets Account from DB: crud_account.crud_account.get(db, id=account_id)
   ├─ Creates AWS clients: aws_client_factory.get_clients_for_account(account)
   │  └─ Calls: assume_role(role_arn=account.role_arn, external_id=account.external_id)
   ├─ Fetches resources: aws_resource_fetchers.fetch_*()
   ├─ Compares with Terraform: drift_engine.compare()
   ├─ Updates Scan model:
   │  - Set status = "running"
   │  - Set status = "completed" with results
   │  - On error: status = "failed" with error message
   └─ Publishes events if drift detected

c) AWS Client Factory: get_clients_for_account()
   ├─ Expects account object with:
   │  - account.role_arn (required)
   │  - account.external_id (optional)
   ├─ Calls: assume_role(role_arn, external_id)
   │  └─ Uses base AWS credentials from .env
   │  └─ Returns temporary credentials
   ├─ Creates boto3 Session with temp credentials
   └─ Returns dict of service clients

d) AWS Client Factory: assume_role()
   ├─ Reads base AWS credentials from environment:
   │  - CLOUD__AWS_ACCESS_KEY_ID
   │  - CLOUD__AWS_SECRET_ACCESS_KEY
   ├─ Calls: boto3.client("sts").assume_role(RoleArn, ExternalId)
   ├─ Caches credentials in-memory (with safety margin)
   └─ Returns temporary credentials

## 4. REQUIRED CONFIGURATION

For the flow to work end-to-end, you need:

a) AWS Account Registered (ALREADY DONE ✓):
   - Account: 740122274365
   - Role ARN: arn:aws:iam::740122274365:role/iac_driftwatch_role
   - External ID: e3a8a66aa5f8a368b988de75de3221ff (encrypted in DB)

b) Base AWS Credentials in .env (MISSING - NEEDS ACTION):
   
   Option B1: Your own AWS access keys
   Add to .env:
     CLOUD__AWS_ACCESS_KEY_ID=AKIA...
     CLOUD__AWS_SECRET_ACCESS_KEY=...
     CLOUD__PROVIDER=aws
   
   Option B2: Use AWS profile (alternative)
   Set environment variable before starting app:
     export AWS_PROFILE=my-profile
   
   Option B3: Use STS temporary credentials
   Add to .env:
     CLOUD__AWS_ACCESS_KEY_ID=ASIA...
     CLOUD__AWS_SECRET_ACCESS_KEY=...
     CLOUD__AWS_SESSION_TOKEN=...
     CLOUD__PROVIDER=aws

c) IAM Role Trust Relationship (MUST EXIST):
   The role in AWS account 740122274365 must have a trust relationship
   that allows the external identity (your base credentials) to assume it:
   
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "AWS": "arn:aws:iam::YOUR-ACCOUNT-ID:root"  // or specific role/user
         },
         "Action": "sts:AssumeRole",
         "Condition": {
           "StringEquals": {
             "sts:ExternalId": "e3a8a66aa5f8a368b988de75de3221ff"
           }
         }
       }
     ]
   }

## 5. TESTING THE FLOW

Step 1: Add AWS credentials to .env
  CLOUD__AWS_ACCESS_KEY_ID=AKIA...
  CLOUD__AWS_SECRET_ACCESS_KEY=...
  CLOUD__PROVIDER=aws

Step 2: Restart the application
  Ctrl+C in terminal with uvicorn
  python -m uvicorn main:app --reload

Step 3: Test endpoint
  curl -X POST http://127.0.0.1:8000/accounts/1/scans \
    -H "Authorization: Bearer <YOUR_TOKEN>" \
    -H "Content-Type: application/json"
  
  Response:
  {
    "id": 2,
    "scan_id": "scan_2",
    "account_id": 1,
    "status": "queued",
    "result": null,
    "error": null,
    "created_at": "2025-09-01T10:30:00",
    "updated_at": "2025-09-01T10:30:00"
  }

Step 4: Poll for results
  curl http://127.0.0.1:8000/accounts/1/scans/scan_2 \
    -H "Authorization: Bearer <YOUR_TOKEN>"
  
  After a few seconds, status changes to "running"
  After processing, status changes to "completed" with result object
  
  On error, status = "failed" with error message

Step 5: View drift results
  curl http://127.0.0.1:8000/accounts/1/scans/scan_2/drift \
    -H "Authorization: Bearer <YOUR_TOKEN>"
  
  Returns: List of drift items (resources with differences)

## 6. ERROR HANDLING

If assume_role fails:
  InvalidClientTokenId
    → Base AWS credentials are invalid or missing
    → Check .env CLOUD__AWS_* variables
  
  AccessDenied
    → Base credentials don't have sts:AssumeRole permission
    → Check IAM policies for base credentials
  
  NoCredentialsError
    → No AWS credentials found at all
    → Check .env and AWS_* environment variables

If resource fetch fails:
  → Check that assumed role has read permissions for that service
  → E.g., ec2:DescribeInstances, s3:ListBuckets, iam:ListRoles

## 7. CURRENT STATUS

✓ Endpoint: Fully implemented
✓ Database: Scans table created with all columns
✓ Account fetching: Working (get account by ID from DB)
✓ Account details: role_arn and external_id available
✓ AWS client factory: Fully implemented
✓ Orchestrator: Fully implemented with error handling
✓ Resource fetchers: Implemented for EC2, S3, IAM, RDS, Security Groups
✓ Scan status tracking: Implemented (queued → running → completed/failed)
✓ Result persistence: Implemented (result and error fields)

✗ AWS credentials: MISSING from .env (ACTION REQUIRED)

NEXT STEP: Add AWS credentials to .env file and test the flow.
"""
