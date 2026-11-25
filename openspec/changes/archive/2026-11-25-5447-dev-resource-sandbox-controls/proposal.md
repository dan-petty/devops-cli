# Proposal: #5447

## Why
`SECURITY.md` states the security controls, but it has no rule for when a control may change for a dedicated development resource or a sandbox. Each exception is argued again, and agents face avoidable refusals inside bounded environments.

## What Changes
- Expand `## Dedicated Development Resources and Sandboxes` in `SECURITY.md` with the policy rules (`**Default.**`, `**Conditions.**`, `**Never changed.**`, `**Approval.**`) and the list of dedicated resources and sandboxes by role, keeping the six-column control table and existing owner-approved Trivy entries.
- Link `../../SECURITY.md#dedicated-development-resources-and-sandboxes` from `docs/guidelines/agentic-jobs.md` (tuning loop step 3) and `docs/guidelines/sre.md` (Table 1).
- Add invariant tests in `tests/invariants/test_agents_md.py` and `tests/invariants/test_guidelines.py` that enforce the section rules, six-column table shape, `YYYY-MM-DD` review date format, empty-table support, and guideline links.

## Capabilities

### New Capabilities
- `security-controls-policy`: Policy rules, role list, control exception table validation, and guideline links for dedicated development resources and sandboxes.

## Impact
Documentation and invariant tests only (`SECURITY.md`, `docs/guidelines/agentic-jobs.md`, `docs/guidelines/sre.md`, `tests/invariants/test_agents_md.py`, `tests/invariants/test_guidelines.py`). No runtime behavior changes.

## Feasibility
Confirmed against `origin/main`: `SECURITY.md` holds `## Dedicated Development Resources and Sandboxes` with the six-column table and two Trivy rows from #4361, while the policy lead-ins, resource roles, guideline links, and invariant tests are not yet present.

## Existing Tool Considered
Uses the existing policy-as-documentation pattern in `SECURITY.md` and parses tables with `tests/support/markdown_tables.py` (`markdown-it-py`, already a declared dependency). Estimated build cost: 0.2M tokens and 1 hour.
