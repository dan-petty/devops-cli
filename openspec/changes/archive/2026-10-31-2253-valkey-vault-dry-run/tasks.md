# Tasks

## 1. Implementation
- [x] 1.1 Create `src/devops_cli/valkey/valkey_plans.py` with plan generators for 9 Valkey commands
- [x] 1.2 Create `src/devops_cli/security/vault_plans.py` with plan generators for 7 Vault commands
- [x] 1.3 Update `src/devops_cli/commands/valkey.py` to annotate 9 commands with `@dry_run_class("request-plan")`, add `--dry-run` where missing, remove legacy `@dry_run_command`, and wire request planning
- [x] 1.4 Update `src/devops_cli/commands/vault.py` to annotate 7 commands with `@dry_run_class("request-plan")`, annotate `vault audit` with `@dry_run_class("no-external-request")`, remove legacy `render_dry_run_result`, and wire request planning
- [x] 1.5 Remove the 17 Valkey and Vault commands from `tests/fixtures/dry_run_gaps.json`

## 2. Verification
- [x] 2.1 Add unit tests in `tests/commands/test_valkey_vault_dry_run.py` verifying dry-run classifications, request plans, and zero external calls
- [x] 2.2 Update existing tests in `tests/commands/test_valkey.py` and `tests/commands/test_vault_cmd.py` to assert new request plan outputs
- [x] 2.3 Verify ratchet tests and full test suites pass
- [x] 2.4 Run full `devops ci` check
