"""
SCAN ENDPOINT ARCHITECTURE DIAGRAM & SUMMARY
==============================================

## ARCHITECTURE DIAGRAM

┌─────────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI ENDPOINT                                     │
│                 POST /accounts/{account_id}/scans                          │
│                                                                             │
│  User Request → Authenticate (JWT Token) → Authorization (RBAC) → Handler │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ENDPOINT HANDLER (create_scan)                        │
│                    app/api/v1/endpoints/accounts.py                        │
│                                                                             │
│  1. Get account from DB (validated by deps.get_required_account)          │
│  2. Check account is active                                                │
│  3. Create Scan record: Scan(account_id=account.id, status="queued")      │
│  4. Save to database                                                       │
│  5. Queue background task                                                  │
│  6. Return: ScanOut (id, scan_id, account_id, status="queued", ...)       │
│  7. Response: 202 ACCEPTED (background_tasks.add_task)                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BACKGROUND TASK (Async Orchestrator)                    │
│              app/services/drift_orchestrator.py::orchestrate_account_scan  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ 1. Get database session (if not provided)                           │ │
│  │ 2. Retrieve Scan record from database                               │ │
│  │ 3. Update scan.status = "running"                                   │ │
│  │ 4. Commit to database                                               │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ FETCH ACCOUNT FROM DATABASE                                         │ │
│  │                                                                      │ │
│  │ Get account by ID from AwsAccount table                            │ │
│  │ Retrieved fields:                                                   │ │
│  │   - account.id (internal)                                          │ │
│  │   - account.account_id (AWS 12-digit ID)                           │ │
│  │   - account.name (e.g., "project_account")                         │ │
│  │   - account.role_arn (e.g., "arn:aws:iam::740122274365:...")       │ │
│  │   - account.external_id (encrypted, used for cross-account access) │ │
│  │   - account.is_active (boolean)                                     │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ CREATE AWS CLIENTS                                                  │ │
│  │ aws_client_factory.get_clients_for_account(account)                 │ │
│  │                                                                      │ │
│  │ For each service (ec2, s3, iam, rds):                              │ │
│  │   1. Call: get_boto3_client(account, service)                      │ │
│  │   2. Assume role: assume_role(                                     │ │
│  │        role_arn=account.role_arn,                                  │ │
│  │        external_id=account.external_id                             │ │
│  │      )                                                              │ │
│  │   3. STS AssumeRole API call to AWS:                               │ │
│  │        boto3.sts.assume_role(                                      │ │
│  │          RoleArn="arn:aws:iam::740122274365:role/...",             │ │
│  │          ExternalId="e3a8a66aa5f8a368...",                         │ │
│  │          RoleSessionName="driftwatch-session"                      │ │
│  │        )                                                            │ │
│  │   4. Get temporary credentials from response                       │ │
│  │   5. Cache credentials in-memory (until expiration)                │ │
│  │   6. Create boto3 Session with temp credentials                    │ │
│  │   7. Create service client (ec2, s3, etc.)                         │ │
│  │   8. Return client dict: {ec2: client, s3: client, ...}            │ │
│  │                                                                      │ │
│  │ AWS Credentials Flow:                                              │ │
│  │   Base credentials (from .env/environment)                         │ │
│   │     ↓                                                              │ │
│  │   boto3.sts.assume_role()  [STS API Call]                         │ │
│  │     ↓                                                              │ │
│  │   Temporary credentials for target account/role                    │ │
│  │     ↓                                                              │ │
│  │   boto3 Session & Clients                                          │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ FETCH LIVE RESOURCES FROM AWS                                       │ │
│  │ aws_resource_fetchers.*()                                           │ │
│  │                                                                      │ │
│  │ For each resource type:                                            │ │
│  │   - fetch_ec2_instances(ec2_client)                                │ │
│  │   - fetch_security_groups(ec2_client)                              │ │
│  │   - fetch_rds_instances(rds_client)                                │ │
│  │   - fetch_s3_buckets(s3_client)                                    │ │
│  │   - fetch_iam_roles(iam_client)                                    │ │
│  │                                                                      │ │
│  │ Each fetcher:                                                      │ │
│  │   1. Calls AWS API (with pagination)                               │ │
│  │   2. Retries up to 3 times on transient failures                   │ │
│  │   3. Returns list of raw resource dicts                            │ │
│  │                                                                      │ │
│  │ Result: live_resources = {                                         │ │
│  │   "ec2_instances": [...],                                          │ │
│  │   "security_groups": [...],                                        │ │
│  │   "rds_instances": [...],                                          │ │
│  │   "s3_buckets": [...],                                             │ │
│  │   "iam_roles": [...]                                               │ │
│  │ }                                                                   │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ LOAD TERRAFORM REFERENCE                                           │ │
│  │ _load_terraform_reference()                                        │ │
│  │                                                                      │ │
│  │ 1. Scan /terraform directory for *.tf files                        │ │
│  │ 2. Parse each Terraform file                                       │ │
│  │ 3. Extract resource definitions                                    │ │
│  │ 4. Normalize to standard format                                    │ │
│  │ 5. Return list of desired resources                                │ │
│  │                                                                      │ │
│  │ Result: tf_resources = [                                           │ │
│  │   {resource_type: "aws_s3_bucket", ...},                           │ │
│  │   {resource_type: "aws_ec2_instance", ...},                        │ │
│  │   ...                                                              │ │
│  │ ]                                                                   │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ DETECT DRIFT                                                        │ │
│  │ drift_engine.compare(tf_resources, live_resources)                 │ │
│  │                                                                      │ │
│  │ 1. Compare desired (Terraform) vs actual (AWS) state              │ │
│  │ 2. Find resources that:                                            │ │
│  │    - Exist in Terraform but not in AWS (drift)                    │ │
│  │    - Exist in AWS but not in Terraform (unmanaged)                │ │
│  │    - Exist in both but have different configuration                │ │
│  │ 3. Assign severity levels (low, medium, high, critical)            │ │
│  │ 4. Generate detailed diff for each drift                           │ │
│  │                                                                      │ │
│  │ Result: comparison = {                                             │ │
│  │   "drifts": [                                                      │ │
│  │     {                                                              │ │
│  │       "resource_id": "...",                                        │ │
│  │       "resource_type": "aws_s3_bucket",                            │ │
│  │       "change_type": "modified|added|removed",                     │ │
│  │       "severity": "low|medium|high|critical",                      │ │
│  │       "diff": {...}                                                │ │
│  │     },                                                             │ │
│  │     ...                                                            │ │
│  │   ]                                                                │ │
│  │ }                                                                   │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ PERSIST RESULTS                                                     │ │
│  │                                                                      │ │
│  │ 1. Save resources to tracked_resources table                       │ │
│  │ 2. Save drift records to drift_records table                       │ │
│  │ 3. Update scan.status = "completed"                                │ │
│  │ 4. Set scan.result = comparison (JSON)                             │ │
│  │ 5. Publish DriftDetectedEvent if drift found                       │ │
│  │ 6. Commit all changes to database                                  │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ RETURN TO CALLER                                                    │ │
│  │                                                                      │ │
│  │ Background task complete                                           │ │
│  │ Scan record in database is now:                                    │ │
│  │   - status = "completed" (or "failed" on error)                    │ │
│  │   - result = comparison dict (or null if failed)                   │ │
│  │   - error = error message (or null if successful)                  │ │
│  │   - updated_at = current timestamp                                 │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘

## DATABASE SCHEMA

aws_accounts TABLE:
  ├─ id (INT, PK)
  ├─ account_id (VARCHAR 12, unique) ← AWS 12-digit account number
  ├─ name (VARCHAR 255)
  ├─ role_arn (VARCHAR 255) ← Used for assume_role
  ├─ external_id (VARCHAR 255) ← Used for assume_role
  ├─ is_active (BOOLEAN)
  ├─ created_at (DATETIME)
  └─ updated_at (DATETIME)

scans TABLE:
  ├─ id (INT, PK) ← Internal scan ID
  ├─ account_id (INT, FK → aws_accounts.id)
  ├─ status (VARCHAR 20) ← "queued", "running", "completed", "failed"
  ├─ result (JSON) ← Comparison results (drifts, etc.)
  ├─ error (VARCHAR 2000) ← Error message if status="failed"
  ├─ created_at (DATETIME)
  └─ updated_at (DATETIME)

GET /accounts/1/scans/scan_1 returns:
  {
    "id": 1,
    "scan_id": "scan_1",  ← Public ID (scan_{id})
    "account_id": 1,
    "status": "completed",
    "result": {
      "drifts": [
        {
          "resource_id": "my-bucket",
          "resource_type": "aws_s3_bucket",
          "change_type": "modified",
          "severity": "medium",
          "diff": {"versioning": {"old": "off", "new": "on"}}
        }
      ]
    },
    "error": null,
    "created_at": "2025-09-01T12:30:00",
    "updated_at": "2025-09-01T12:35:00"
  }

## STATUS FLOW

Client Request
      ↓
Endpoint returns 202 ACCEPTED with scan_id
      ↓
Background task starts
      ↓
scan.status = "queued" → "running"
      ↓
Fetch AWS resources
      ↓
Compare with Terraform
      ↓
scan.status = "running" → "completed" OR "failed"
      ↓
GET /accounts/{account_id}/scans/{scan_id} to check status
      ↓
Response shows final status and results

## KEY FILES

1. Endpoint:
   app/api/v1/endpoints/accounts.py::create_scan()

2. Orchestrator:
   app/services/drift_orchestrator.py::orchestrate_account_scan()

3. AWS Client Factory:
   app/services/aws_client_factory.py::get_clients_for_account()
   app/services/aws_client_factory.py::assume_role()

4. Resource Fetchers:
   app/services/aws_resource_fetchers.py::fetch_*()

5. Drift Engine:
   app/drift/engine.py::compare()

6. Models:
   app/models/account.py::AwsAccount
   app/models/scan.py::Scan

7. Schemas:
   app/schemas/scan.py::ScanOut

8. CRUD:
   app/crud/crud_account.py::CRUDAccount

## CURRENT STATUS

✓ All code is implemented and connected
✓ Database tables created
✓ Account registered with credentials
✓ Endpoints ready
✓ Background task system ready
✓ Orchestrator ready
✓ AWS client factory ready
✓ Resource fetchers ready

✗ Missing: AWS credentials in .env file

## NEXT STEP

Add AWS credentials to .env file and restart application!
"""
