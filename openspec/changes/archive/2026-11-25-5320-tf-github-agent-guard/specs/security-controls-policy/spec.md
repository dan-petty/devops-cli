## ADDED Requirements

### Requirement: GitHub Settings security controls section
`SECURITY.md` SHALL include a `## GitHub Settings` section stating the `tf.stacks[].agent_access` `plan` default and agent refusal for apply and destroy, the pre-plan `DEFAULT_TF_GITHUB_CORE_BUDGET_FLOOR` check, the fail-closed `tf.github_reader` reader App credentials, and zero-request `--dry-run` behavior.

#### Scenario: Docs check passes with GitHub Settings section
- **WHEN** `uv run devops ci --check --only docs` runs
- **THEN** the `docs` gate passes and `SECURITY.md` documents the GitHub settings controls
