# Tasks

## 1. Dry-run class infrastructure and ratchet test

Reads: `src/devops_cli/dry_run/decorator.py`, `src/devops_cli/core/command_resolver.py`, `src/devops_cli/config/constants.py`.. Changes: `src/devops_cli/dry_run/decorator.py`, `src/devops_cli/dry_run/__init__.py`, `src/devops_cli/core/command_resolver.py`, `tests/test_dry_run_class_ratchet.py`, `tests/fixtures/dry_run_gaps.json`, `tests/test_main_dry_run.py`..

- [x] 1.1 Write unit and invariant tests in `tests/test_dry_run_class_ratchet.py` that check criteria 1-7 (ratchet enforcement, gap list validity, dry-run option requirement for request-plan commands, lazy proxy execution for no-external-request commands, and MCP exposure table consistency). Confirm the tests fail before implementation.
- [x] 1.2 Implement the `@dry_run_class` decorator and `get_dry_run_class` in `src/devops_cli/dry_run/decorator.py` and export them in `src/devops_cli/dry_run/__init__.py`. Update `resolve_proxy_dry_run` in `src/devops_cli/core/command_resolver.py` to route `no-external-request` commands without `--dry-run`.
- [x] 1.3 Apply `@dry_run_class("request-plan")` to the 32 distinct commands that implement request plans in `src/devops_cli/commands/ci.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/commands/gh.py`, `src/devops_cli/commands/k8s/diagnostics.py`, `src/devops_cli/commands/k8s/cluster_secret_push.py`, `src/devops_cli/commands/k8s/cluster_jobs.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `src/devops_cli/commands/k8s/volume.py`, and `src/devops_cli/commands/review.py`. Generate `tests/fixtures/dry_run_gaps.json` with the remaining unclassified command paths.
- [x] 1.4 Remove the obsolete test `test_invariants_all_dry_run_commands_consistent` and `_collect_command_dry_run_info` in `tests/test_main_dry_run.py`. Confirm `tests/test_dry_run_class_ratchet.py` and `tests/test_main_dry_run.py` pass.
- [x] 1.5 Regenerate documentation with `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci` passes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
