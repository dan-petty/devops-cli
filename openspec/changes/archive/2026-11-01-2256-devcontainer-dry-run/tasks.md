# Tasks: Dry-Run Classification for Devcontainer and Install-Tools Commands

## 1. Plan Builders and Helpers
- [x] 1.1 Create plan functions in `src/devops_cli/devcontainer/devcontainer_plans.py` for `bootstrap-k8s`, `post-create`, `post-start`, `run-lifecycle`, `unlock-keyring`, and `install-tools`

## 2. Classify and Implement Commands
- [x] 2.1 Annotate `devcontainer bootstrap-k8s` with `@dry_run_class("request-plan")`, add `--json` support, and render planned Minikube commands
- [x] 2.2 Annotate `devcontainer post-create` with `@dry_run_class("request-plan")`, add `--json` support, and render planned tool installations
- [x] 2.3 Annotate `devcontainer post-start` with `@dry_run_class("request-plan")`, add `--json` support, and render planned git and kubectl context requests
- [x] 2.4 Annotate `devcontainer run-lifecycle` with `@dry_run_class("request-plan")`, add `--json` support, and render planned lifecycle requests based on flags
- [x] 2.5 Annotate `devcontainer unlock-keyring` with `@dry_run_class("request-plan")`, add `--dry-run` and `--json` support, and render planned keyring unlock and gh auth requests
- [x] 2.6 Annotate `install-tools` (`install_all`) with `@dry_run_class("request-plan")`, add `--dry-run` and `--json` support, and render planned downloads and installer executions
- [x] 2.7 Annotate `devcontainer init` with `@dry_run_class("no-external-request")` and add `--dry-run` local preview
- [x] 2.8 Annotate `devcontainer update` with `@dry_run_class("no-external-request")` and add `--dry-run` local preview
- [x] 2.9 Annotate `devcontainer list` and `devcontainer validate` with `@dry_run_class("no-external-request")`, removing echo-only dry-run options and previews
- [x] 2.10 Annotate `install-tools status` with `@dry_run_class("no-external-request")`

## 3. Invariants and Fixtures
- [x] 3.1 Remove the 11 commands from `tests/fixtures/dry_run_gaps.json`
- [x] 3.2 Verify `tests/invariants/test_dry_run_class_ratchet.py` passes

## 4. Test Coverage and Documentation
- [x] 4.1 Create `tests/commands/test_devcontainer_install_tools_dry_run.py` to test dry runs, tripwires, and plan accuracy across all 11 commands
- [x] 4.2 Update existing tests in `tests/commands/test_devcontainer.py` and `tests/commands/test_install_tools.py`
- [x] 4.3 Synchronize CLI documentation via `uv run devops docs generate --sync-readme`
