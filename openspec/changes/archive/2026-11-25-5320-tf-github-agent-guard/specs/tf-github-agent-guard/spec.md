## ADDED Requirements

### Requirement: Agent access level for tf/github stacks
`tf.stacks[].agent_access` SHALL accept only `plan` or `apply` and SHALL default to `plan` for every `tf/github` stack. Invalid values (such as `full`) SHALL raise a configuration error naming `tf.stacks[].agent_access`, `plan`, and `apply`. When `is_agent_caller()` reports an agent caller, `devops tf apply` and `devops tf destroy` SHALL exit 1 before invoking `tofu` unless `agent_access` is `apply`, while person sessions remain permitted at `plan`.

#### Scenario: Agent apply refused at plan level and allowed at apply level
- **WHEN** an agent caller invokes `devops tf apply` or `devops tf destroy` on a `tf/github` stack with default (`plan`) access
- **THEN** the command exits 1 naming `tf.stacks[].agent_access` with zero `tofu` calls, whereas `apply` level allows the run and a person caller passes at `plan` level

### Requirement: Pre-plan core budget floor, reader App credentials, and zero-request dry run
`devops tf plan` on a `tf/github` stack SHALL check `get_github_rate_limiter().get_quota("core")` against `DEFAULT_TF_GITHUB_CORE_BUDGET_FLOOR` (250) and exit 1 naming the remaining budget and floor without calling `tofu` when valid quota is below 250. Non-dry-run agent plans SHALL mint an installation token for `devops-settings-reader` using `tf.github_reader.app_id`, `tf.github_reader.installation_id`, and `tf.github_reader.private_key` without reading writer App credentials, and SHALL exit 1 naming all three keys when incomplete. `--dry-run` checks access and budget without starting `tofu`, reading credentials, or sending requests.

#### Scenario: Budget floor and reader credentials protect agent plans
- **WHEN** core quota is 249 or `tf.github_reader` credentials are missing
- **THEN** `devops tf plan` exits 1 with zero `tofu` calls; when quota is sufficient and reader credentials exist, the `tofu` child receives the reader `GITHUB_TOKEN`
