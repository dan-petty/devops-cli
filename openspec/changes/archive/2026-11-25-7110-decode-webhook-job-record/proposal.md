# Proposal: #7110

## Why
`issue_from_event` in `src/devops_cli/roadmap/stores/brain_issues.py` passes the raw dictionary from `split_record` into `IssueRecord` without calling `decode_job_record`. Live `roadmap-service` webhooks fail Pydantic validation on `job_record.implement.repair_rounds` when that field is an integer. Closes #7110.

## What Changes
- Call `decode_job_record` on the dictionary that `split_record` returns in `issue_from_event` (`src/devops_cli/roadmap/stores/brain_issues.py`).
- Add regression tests in `tests/server/routes/test_webhooks_brain.py` for incoming `issues` and `issue_comment` deliveries whose issue body holds `implement.repair_rounds` as an integer alongside unknown or non-string record fields.

This change alters observable webhook delivery and project-brain caching behavior, so it adds a requirement to `project-brain/shared-cache`. It fits one pull request.

## Capabilities
- `project-brain/shared-cache`: decode webhook job records through `decode_job_record` before constructing `IssueRecord`.

## Impact
- `roadmap-service` webhook handlers (`_remember_delivery_issue`) stop raising unhandled Pydantic validation errors on issues that carry integer record values or unknown keys.

## Feasibility
Confirmed against `origin/main` source (`src/devops_cli/roadmap/stores/brain_issues.py:76-94`, `src/devops_cli/roadmap/stores/store.py:1042-1076`, `src/devops_cli/roadmap/stores/github_store.py:252`) and live cluster Loki logs from `roadmap-service` on `2026-11-25` showing `pydantic_core._pydantic_core.ValidationError` for `job_record.implement.repair_rounds` (`input_value=0`, `input_value=2`).

## Existing Tool Considered
`decode_job_record` in `src/devops_cli/roadmap/stores/store.py:1042` already converts `implement.repair_rounds` from integer to text and filters unknown or invalid values. No external library is necessary. Calling the existing helper reuses one source of truth at near-zero token cost and deletes no code.
