## ADDED Requirements

### Requirement: One plan job per pull request head
A `pull_request` `synchronize` delivery for an open infra pull request SHALL create exactly one `infra-plan` Job for that head.

#### Scenario: Two deliveries for one head create one Job
- **WHEN** `uv run pytest tests/server/test_server_infra_plan.py -q` runs with two `synchronize` deliveries for the same pull request head
- **THEN** the launcher creates one `infra-plan` Job with the repository, the pull request number and the head, and the second delivery gets the existing unit

### Requirement: Plan comment is one and updates
The `infra-plan` step SHALL post one plan comment with the marker `<!-- devops roadmap infra-plan -->` and SHALL edit that comment on the next push.

#### Scenario: Second run edits the first comment
- **WHEN** `uv run pytest tests/roadmap/steps/test_roadmap_step_infra_plan.py -q` runs the step twice with a fake GitHub client
- **THEN** the first run creates one comment with the marker, and the second run edits that comment and creates no other

### Requirement: Access level gates the plan step
The `infra-plan` step SHALL run only when the agent access level of the infra repo is `plan` or higher.

#### Scenario: Repo at none gets no plan
- **WHEN** `uv run pytest tests/roadmap/steps/test_roadmap_step_infra_plan.py -q` runs with an infra repo at level `none`
- **THEN** the step exits 0, posts no plan comment, and records that `infra.repos[].agent_access` refused the run
