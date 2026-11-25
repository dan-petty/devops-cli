# security-controls-policy Specification

## Purpose

Rules, conditions, never-changed invariants, role list, and exception control table in `SECURITY.md` for dedicated development resources and sandboxes, together with links from the SRE and agentic-jobs guidelines and invariant tests.

## Requirements

### Requirement: Security section for dedicated resources and sandboxes
`SECURITY.md` SHALL hold a top-level section `Dedicated Development Resources and Sandboxes` (anchor `#dedicated-development-resources-and-sandboxes`) that states the default, the conditions, the never-changed rules and the approval rule, lists the dedicated development resources and sandboxes by role, and holds the control table with the header `Control`, `Scope`, `Compensating control`, `Evidence`, `Approved by` and `Reviewed`.

#### Scenario: The section holds each rule and the table
- **WHEN** `uv run pytest tests/invariants/test_agents_md.py` reads the section between the `## Dedicated Development Resources and Sandboxes` heading and the next `## ` heading.
- **THEN** the test passes only when the section holds the `**Default.**`, `**Conditions.**`, `**Never changed.**` and `**Approval.**` lead-ins, names the owner as the approver, names the homelab, the devcontainer, the project-owned test namespaces and repositories, RuntimeClass `gvisor`, the review sandbox and the planner run Job, and holds the table header `Control | Scope | Compensating control | Evidence | Approved by | Reviewed`.

### Requirement: Control table row fields
Every data row of the control table SHALL have a non-empty `Control`, `Scope`, `Compensating control`, `Evidence`, `Approved by` and `Reviewed` cell.

#### Scenario: A row misses a required field
- **WHEN** a data row has an empty cell in one of the six columns.
- **THEN** validation fails and names the row and the missing column.

### Requirement: Empty control table
The control table SHALL accept a header with no data rows.

#### Scenario: No exception is recorded
- **WHEN** the table holds its header row and no data row.
- **THEN** validation passes.

### Requirement: Review date format
The `Reviewed` cell of each data row SHALL be an ISO 8601 calendar date in the form `YYYY-MM-DD`.

#### Scenario: Invalid review date
- **WHEN** a data row has a `Reviewed` value that is not a `YYYY-MM-DD` date.
- **THEN** validation fails and names the row and the value.

### Requirement: Guideline links to the section
`docs/guidelines/agentic-jobs.md` and `docs/guidelines/sre.md` SHALL link to `../../SECURITY.md#dedicated-development-resources-and-sandboxes`.

#### Scenario: Both guidelines link the section
- **WHEN** `uv run pytest tests/invariants/test_guidelines.py` reads the two guideline files.
- **THEN** the test passes only when each file holds an inline link whose target is `../../SECURITY.md#dedicated-development-resources-and-sandboxes`.

### Requirement: No host name in the resource list
The resource list SHALL name each resource by role and hold no internal host name or private address.

#### Scenario: The address invariant reads the policy
- **WHEN** a person runs `uv run pytest tests/invariants/test_committed_addresses.py` after the section is added.
- **THEN** the test passes.

### Requirement: Documentation check
The changed documents SHALL pass the documentation check.

#### Scenario: Docs check passes
- **WHEN** a person runs `uv run devops docs check`.
- **THEN** the command exits 0.

### Requirement: GitHub Settings security controls section
`SECURITY.md` SHALL include a `## GitHub Settings` section stating the `tf.stacks[].agent_access` `plan` default and agent refusal for apply and destroy, the pre-plan `DEFAULT_TF_GITHUB_CORE_BUDGET_FLOOR` check, the fail-closed `tf.github_reader` reader App credentials, and zero-request `--dry-run` behavior.

#### Scenario: Docs check passes with GitHub Settings section
- **WHEN** `uv run devops ci --check --only docs` runs
- **THEN** the `docs` gate passes and `SECURITY.md` documents the GitHub settings controls
