# Tasks

## Implementation Tasks

- [x] 1. Add failing tests in `tests/github/test_gh_api_status_branch_protection_secrets_dry_run.py` verifying dry run output and zero external calls for all 9 commands.
- [x] 2. Update `src/devops_cli/github/branch_protection.py` and `src/devops_cli/github/secrets.py` to add request planning builders.
- [x] 3. Update `src/devops_cli/github/metrics.py` and `src/devops_cli/telemetry/service_status.py` to add request planning builders.
- [x] 4. Wire `@dry_run_class("request-plan")`, `--dry-run` options, and request plan previews in `src/devops_cli/commands/gh.py` and `src/devops_cli/commands/status_cmd.py`.
- [x] 5. Remove the 9 command keys from `tests/fixtures/dry_run_gaps.json` and keep list sorted.
- [x] 6. Regenerate documentation with `uv run devops docs generate --sync-readme`.
- [x] 7. Verify all unit tests, ratchet invariant tests, and diff coverage >= 90%.
- [x] 8. Archive OpenSpec change folder with `uv run devops openspec archive 2237-gh-api-status-branch-protection-secrets`.
