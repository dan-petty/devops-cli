# Tasks

## Implementation Tasks

- [x] 1. Add failing tests in `tests/commands/test_pr_dry_run.py` verifying dry run output and zero external calls for all 17 commands.
- [x] 2. Create `src/devops_cli/github/pr_plans.py` with argument builders and request planners for `pr` commands.
- [x] 3. Update `src/devops_cli/github/pr_threads.py` to add `unresolve_thread_args`.
- [x] 4. Wire `@dry_run_class("request-plan")`, `--dry-run` options, and request plan previews across all 17 commands in `src/devops_cli/commands/pr.py`.
- [x] 5. Remove the 17 command keys from `tests/fixtures/dry_run_gaps.json` and keep list sorted.
- [x] 6. Regenerate documentation with `uv run devops docs generate --sync-readme`.
- [x] 7. Verify all unit tests, ratchet invariant tests, and diff coverage >= 90%.
- [x] 8. Archive OpenSpec change folder with `uv run devops openspec archive 2234-pr-dry-run`.
