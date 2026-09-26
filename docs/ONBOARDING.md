# Onboarding: Register a Target AWS Account

Overview
--------
This guide explains how to register a new target AWS account with DriftWatch. The process has two main steps:

1. Deploy the `DriftWatchReadOnlyRole` in the target account.
2. Register the account with the DriftWatch service by calling `POST /api/v1/accounts`.

Pre-requisites
--------------
- Admin or sufficient privileges to deploy an IAM role into the target AWS account.
- Access to the DriftWatch management API (API URL and an API token).
- Account identifier for the target AWS account (12-digit AWS Account ID).

Step 1 — Deploy the `DriftWatchReadOnlyRole`
------------------------------------------
The role should be deployed into the target account and configured to allow DriftWatch to assume it.

Options:

- Terraform module (example usage):

```
module "driftwatch_role" {
  source     = "git::ssh://git.example.com/infra/modules.git//DriftWatchReadOnlyRole"
  account_id = "123456789012"
  role_name  = "DriftWatchReadOnlyRole"
  external_id = "optional-external-id"
}
```

- CloudFormation/Console: deploy the provided `DriftWatchReadOnlyRole` template or your copy with the same role name and trust policy.

Important settings for the role:

- Role name: `DriftWatchReadOnlyRole` (use the agreed name or record the used name).
- Trust policy: allow the DriftWatch service principal (or management account) to assume the role. If the service requires an `ExternalId`, include it and record the value.
- Permissions: grant read-only permissions needed to inventory resources (e.g., `Describe*`, `Get*`, list and read S3 objects if applicable). The module should scope permissions to minimal required actions.

Verify the role (quick test):

```
aws sts assume-role \
  --role-arn arn:aws:iam::123456789012:role/DriftWatchReadOnlyRole \
  --role-session-name driftwatch-test
```

Step 2 — Register the account with DriftWatch
---------------------------------------------
Once the role is deployed and verified, register the account with the management API.

Endpoint (example): `POST /api/v1/accounts`

Request body (JSON):

```
{
  "account_id": "123456789012",
  "role_arn": "arn:aws:iam::123456789012:role/DriftWatchReadOnlyRole",
  "external_id": "OPTIONAL_EXTERNAL_ID"
}
```

curl example:

```
curl -X POST "https://api.example.com/api/v1/accounts" \
  -H "Authorization: Bearer $DRIFTWATCH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"account_id":"123456789012","role_arn":"arn:aws:iam::123456789012:role/DriftWatchReadOnlyRole","external_id":"OPTIONAL_EXTERNAL_ID"}'
```

Successful response:

- The API should return a 201/200 and a record for the registered account. The response may include status and next steps (for example, verification or initial inventory job queued).

Post-registration checks
------------------------
- Confirm the account appears in the DriftWatch UI or via `GET /api/v1/accounts`.
- Watch initial inventory and drift scan logs for permission errors — common issues indicate missing `List`/`Describe` permissions or an incorrect trust policy.

Troubleshooting
---------------
- `AccessDenied` during assume-role: verify trust policy allows the DriftWatch principal and that `ExternalId` matches (if used).
- Missing permissions in API responses: ensure the role has the required read-only actions for the resource types you expect to inventory.
- Logs: consult service logs and the initial inventory job output for specific failing API calls.

Security notes
--------------
- Use a unique `ExternalId` when possible to prevent confused deputy attacks.
- Limit role permissions to only the actions required for inventory and drift detection.
- Rotate any long-lived credentials used during onboarding and avoid embedding secrets in code or public repos.

Example workflow summary
------------------------
1. Deploy the `DriftWatchReadOnlyRole` into account `123456789012`.
2. Verify you can assume the role with `aws sts assume-role`.
3. Call `POST /api/v1/accounts` with `account_id` and `role_arn`.
4. Verify account registration and monitor initial runs.

Where to record the onboarding
------------------------------
- Open a pull request with the Terraform/CloudFormation change and include example `curl` commands used.
- Add the new account to your inventory or runbook with date, deployer, and any `ExternalId` used.

Revision history
----------------
- Created: initial onboarding guide for registering AWS accounts.
