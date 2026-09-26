# Drift Engine — Ignore Lists & Severity Rules

Purpose
-------
This document explains the tunable parts of the drift detection engine so operators can reduce false-positives without reading source code. It focuses on the per-resource-type ignore lists found in `drift/comparators.py` and the rule table defined in `severity.py`.

Where to look
--------------
- Ignore-lists: `drift/comparators.py` — contains per-resource-type definitions that instruct the comparator to skip specific attributes or paths when comparing desired vs observed state.
- Rule table: `severity.py` — maps detection rules to a severity level and includes human-readable descriptions used by alerts and reports.

Ignore-lists (what they are)
-----------------------------
- Purpose: ignore-lists tell the comparator which attributes or subpaths to exclude from comparisons for a resource type. Common uses: volatile timestamps, provider-assigned IDs, scheduling fields, or fields mutated by upstream services.
- Scope: these are usually keyed by resource type (e.g., `aws_s3_bucket`, `kubernetes_deployment`) and list attribute keys, nested paths, or patterns.

Typical formats and examples
----------------------------
- Simple key list (pseudo example):

- `aws_s3_bucket: ["last_modified", "owner"]`

- Nested path example (pseudo):
- `kubernetes_deployment: ["spec.template.metadata.annotations.build_timestamp"]`

- Pattern matching (if supported):
- `some_resource: ["metadata.annotations.*", "labels.temp_*"]`

How to tune ignore-lists
------------------------
1. Reproduce: Capture a representative false-positive comparison for the affected resource.
2. Identify: Note the exact attribute path shown in the comparator output.
3. Add rule: Append a specific ignore entry scoped to the exact resource type (prefer exact attribute paths over broad patterns).
4. Test locally: Re-run the comparator against a sample of resources to confirm the false-positive is resolved and no real drift is masked.
5. Deploy and monitor: Ship the change and monitor drift reports for a few deploy cycles.

Operator guidance — best practices
---------------------------------
- Prefer narrow, attribute-level ignores to avoid hiding real issues.
- Add comments in the file next to each ignore explaining why it was added and when it can be removed.
- If a field is noisy across many resource types, consider addressing the root cause (e.g., adjust sync logic) instead of broad ignores.
- Keep a short review cadence for ignore-list entries (quarterly) to remove stale ignores.

Severity rule table (what it is)
--------------------------------
- `severity.py` defines a table of detection rules, each with:
  - a rule identifier/name,
  - a severity level (for example: `INFO`, `WARNING`, `CRITICAL`),
  - a short description and optionally remediation guidance.
- This table drives alerting, dashboard priorities, and operator escalation behavior.

How to tune severities
----------------------
1. Catalog: Review the rule table and identify rules currently generating the most noisy alerts.
2. Reclassify: Lower severity for low-impact rules that regularly trigger false-positives; raise for high-impact findings.
3. Add rationale: When changing a severity, add a short comment explaining the reasoning and any compensating controls.
4. Communicate: Notify stakeholders when changing severities that affect alerting or SLOs.

Risk and caveats
----------------
- Ignoring attributes or lowering severities can reduce noise but increases the chance of missing real regressions. Balance noise reduction against safety.
- Always prefer targeted ignores and conservative severity changes.

Known AWS limitation — EC2 ARNs
-------------------------------
- `describe_instances()` does not return an EC2 ARN, while Terraform state includes the computed `arn` for `aws_instance` resources.
- The resulting Terraform-ARN versus live-resource-ARN comparison is an accepted EC2-specific false positive. Do not treat it as evidence of actual EC2 drift.

Operational workflow (example)
------------------------------
1. Incident or noisy alert arrives for `resource X`.
2. Operator inspects comparator output and notes attribute path `a.b.c` is noisy.
3. Add `a.b.c` to the ignore list for `resource X` with a comment and date.
4. Lower the rule severity temporarily if alerts are flooding, then investigate a permanent fix.

Automation and testing
----------------------
- Keep unit tests or sample comparator cases that exercise common ignores to prevent regressions.
- If the codebase exposes a dry-run comparator or a CLI, run it against a representative dataset after changes.

Where to record changes
-----------------------
- Prefer submitting changes via pull request so they are reviewed. Include example before/after comparisons in the PR description.
- Track non-code changes (operational tuning) in the runbook or the change log so future operators understand historical tuning decisions.

Owners & contacts
-----------------
- Drift engine owner: [team/name] — update as appropriate.
- Security/infra contact for severity changes: [team/name].

Revision history
----------------
- Created: initial guidance for tuning `drift/comparators.py` and `severity.py`.
