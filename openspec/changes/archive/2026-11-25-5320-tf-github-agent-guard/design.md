# Design

## Decisions

- Centralize `tf/github` stack guards in `src/devops_cli/tf/access.py` (`prepare_tf_stack_run` -> `require_agent_access`, `check_github_core_budget`, `reader_github_env`), called right after `validate_dir(directory)` in `tf_plan`, `tf_apply`, and `tf_destroy`.
- Default `tf.stacks[].agent_access` to `plan` for `tf/github` stacks (and unconfigured `tf/github` directories), rejecting any value other than `plan` or `apply` with a validator naming `tf.stacks[].agent_access`, `plan`, and `apply`.
- Read `get_github_rate_limiter().get_quota("core")` against `DEFAULT_TF_GITHUB_CORE_BUDGET_FLOOR` (250) without external network requests, so both real plans and `--dry-run` enforce the budget with zero API calls.
- Fail closed when `tf.github_reader.{app_id,installation_id,private_key}` is incomplete on non-dry-run agent plans (naming all three settings and never reading the writer/Service App key), while keeping `--dry-run` free of credential reads and token minting.

## Rejected alternatives

- Reusing `DEFAULT_GH_GRAPHQL_BUDGET_FLOOR`: rejected because GraphQL points differ from the REST core quota consumed by the GitHub OpenTofu provider.
- Calling live `GET /rate_limit` before each plan: rejected because it adds external requests and breaks zero-request dry-run behavior.
- Falling back to writer App credentials when `tf.github_reader` is unset: rejected by ADR 0026 (only a person applies; agents hold read-only reader access).
