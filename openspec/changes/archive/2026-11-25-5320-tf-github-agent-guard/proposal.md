# Proposal: #5320

## Why

An agent session can call `devops tf apply` or `devops tf destroy` against `tf/github` stacks managing GitHub settings (ADR 0026, `#5311`), and provider calls bypass `run_gh` rate pacing. Only a person may apply GitHub settings changes, while agents need read-only `devops-settings-reader` plans gated by a pre-plan REST core quota floor and zero-request `--dry-run` behavior.

## What Changes

- Add `tf.stacks[].agent_access` (`plan` or `apply`, defaulting to `plan` on `tf/github` stacks) and `tf.github_reader.{app_id,installation_id,private_key}` settings (`DEVOPS_CLI_TF_GITHUB_READER_*` and OS keyring `tf_github_reader_private_key`).
- Add `src/devops_cli/tf/access.py` (`require_agent_access`, `check_github_core_budget`, `reader_github_env`, `prepare_tf_stack_run`) and invoke it at the top of `tf_plan`, `tf_apply`, and `tf_destroy` after `validate_dir` and before building or starting `tofu`.
- Add `DEFAULT_TF_GITHUB_CORE_BUDGET_FLOOR: int = 250` in `src/devops_cli/config/defaults.py` checked against `get_github_rate_limiter().get_quota("core")` before `tf/github` plans.
- Mint a read-only installation token for `devops-settings-reader` on non-dry-run agent `tf/github` plans, failing closed without falling back to writer App credentials.
- Document these controls under `## GitHub Settings` in `SECURITY.md` and regenerate CLI/config/error docs.

## Capabilities

- `tf-github-agent-guard`: Enforce `tf.stacks[].agent_access`, REST core budget floor, reader App credentials, and zero-request `--dry-run` for `tf/github` stacks.
- `security-controls-policy`: Document the GitHub settings guard policy in `SECURITY.md`.

## Impact

- `src/devops_cli/tf/access.py`, `src/devops_cli/commands/tf.py`, `src/devops_cli/config/{constants,defaults,env,settings}.py`, `src/devops_cli/exceptions/{__init__,tf}.py`, `src/devops_cli/lang/en/errors.py`, `SECURITY.md`, generated docs, and tests. State-command guards remain deferred to `#7061`.

## Feasibility

Verified against `src/devops_cli/commands/tf.py`, `src/devops_cli/infra/access.py`, `src/devops_cli/github/{app_installation,rate_limiter}.py`, `tests/security/test_config_declarations.py`, and `docs/adr/0026-github-settings-are-opentofu-code-the-owner-applies.md`. Note `tf_state`/`tf_import`/`tf_force_unlock` were moved out of `#5320` into `#7061` by refine (`2026-11-25`). Confirmed new tests fail cleanly before implementation.

## Existing Tool Considered

OpenTofu (`opentofu/opentofu`, MPL-2.0, maintained; `alternatives.verdict: in-use`) runs the `tf/github` stacks and provider calls but provides no `is_agent_caller()` refusal, local `run_gh` core budget floor, zero-request dry-run, or `devops-settings-reader` keyring token minting; wrapper guard cost ~0.5M tokens.
