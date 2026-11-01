# Design: Dry-Run Classification for Devcontainer and Install-Tools Commands

## Context & Architecture
Sub-issue #2256 of parent #886 audits commands in `devcontainer` and `install-tools`.
The dry-run contract defines two classes:
1. `request-plan`: For commands that perform external requests (HTTP, cluster, subprocess contacting outside services). A dry run makes zero external requests and returns the planned requests via `render_request_plan` or structured JSON.
2. `no-external-request`: For commands that execute locally without contacting external networks or remote services.
   - For read-only commands without `--dry-run`, `devops --dry-run <command>` executes the command normally through the lazy proxy.
   - For commands modifying local state (`devcontainer init`, `devcontainer update`), `--dry-run` displays a preview message and skips writes.

## Command Classifications

### 1. Request Plan (6 commands)
- `devcontainer bootstrap-k8s`: Decorated with `@dry_run_class("request-plan")`. Accepts `--dry-run` and `--json`. Under dry-run, renders planned execution of `minikube status`, `minikube start`, and `minikube update-context` without launching child processes.
- `devcontainer post-create`: Decorated with `@dry_run_class("request-plan")`. Accepts `--dry-run` and `--json`. Under dry-run, renders planned installations of developer tools (`uv`, `pre-commit`, `claude`) and managed tools downloads.
- `devcontainer post-start`: Decorated with `@dry_run_class("request-plan")`. Accepts `--dry-run` and `--json`. Under dry-run, renders planned `git config` and `kubectl config` updates.
- `devcontainer run-lifecycle`: Decorated with `@dry_run_class("request-plan")`. Accepts `--dry-run` and `--json`. Under dry-run, renders combined plans for post-create and/or post-start lifecycle phases based on flags (`--post-create`, `--post-start`, `--all`).
- `devcontainer unlock-keyring`: Decorated with `@dry_run_class("request-plan")`. Accepts `--dry-run` and `--json`. Under dry-run, renders planned execution of `gnome-keyring-daemon --replace --unlock`, `gh auth token`, and `gh auth login`.
- `install-tools`: Decorated with `@dry_run_class("request-plan")`. Accepts `--dry-run` and `--json`. Under dry-run, renders planned HTTP downloads and installer commands for locked tools.

### 2. Local Preview (2 commands)
- `devcontainer init`: Decorated with `@dry_run_class("no-external-request")`. Accepts `--dry-run`. Under dry-run, validates inputs and prints `Would create devcontainer configuration in <path>` without creating or writing files.
- `devcontainer update`: Decorated with `@dry_run_class("no-external-request")`. Accepts `--dry-run`. Under dry-run, validates manifest presence and prints `Would update image in <path> to <image>` without modifying `devcontainer.json`.

### 3. Mark Only (3 commands)
Decorated with `@dry_run_class("no-external-request")`:
- `devcontainer list` (remove `--dry-run` and `render_dry_run_result`)
- `devcontainer validate` (remove `--dry-run` and `render_dry_run_result`)
- `install-tools status`

## Invariant and Test Updates
- Remove the 11 commands from `tests/fixtures/dry_run_gaps.json`.
- Add test suite `tests/commands/test_devcontainer_install_tools_dry_run.py` covering all 11 commands, verifying plan accuracy, local previews, and network/process isolation.
- Update `tests/commands/test_devcontainer.py` and `tests/commands/test_install_tools.py` to reflect the removal of echo-only previews.
