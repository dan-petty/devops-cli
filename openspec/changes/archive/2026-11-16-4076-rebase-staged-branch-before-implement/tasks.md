# Tasks: #4076 Rebase staged branch onto main before implement

- [x] 1. CLI option and refusal outside runner
  - [x] 1.1 Add help string `implement_rebase` in `src/devops_cli/lang/en/help.py`
  - [x] 1.2 Add `--no-rebase` to `runner_only_options` in `src/devops_cli/roadmap/implement/implement_outside.py`
  - [x] 1.3 Add `--rebase/--no-rebase` option to `implement_cmd` in `src/devops_cli/commands/roadmap.py` and pass to `_implement_job`
  - [x] 1.4 Add tests for `--no-rebase` outside runner and dry-run in `tests/roadmap/implement/test_roadmap_implement_outside.py`
- [x] 2. Execution and dry run wiring
  - [x] 2.1 Pass `rebase` into `dry_run_implement` and `implement_requests`, omitting rebase request when `rebase=False`
  - [x] 2.2 Add unit test for `implement_requests` with `rebase=False` in `tests/roadmap/test_roadmap_dry_runs.py`
  - [x] 2.3 Update `apply_implement`, `_implement_item`, and `_ItemRun` in `src/devops_cli/roadmap/implement/implement_run.py` to skip sync when `rebase=False`
  - [x] 2.4 Add integration tests for `apply_implement(..., rebase=False)` in `tests/roadmap/implement/test_roadmap_implement_job.py`
- [x] 3. Verification and documentation
  - [x] 3.1 Update CLI reference documentation (`docs/CLI_REFERENCE.md`)
  - [x] 3.2 Run quality gates and verify all checks pass
