# Task: Devcontainer no longer starts Git daemon stub (#1122)

**Issue**: [#1122](https://github.com/dan-petty/devops-cli/issues/1122)
**Status**: Done
**Milestone**: v0.2.31
**Priority**: priority/p2-medium
**Scope**: type/security, priority/p2-medium, scope/security

## Description

The devcontainer previously started `git daemon --reuseaddr --base-path=/workspace/repos --export-all --verbose` during `devops devcontainer post-start` (step 7) and listened on port 9418. The daemon was originally added as a stub for Argo CD integration, which has read from GitHub instead of the local daemon since v0.2.11 (#38). The daemon served clones under `repos/` with `--export-all` without authentication, exposing clones across forwarded port 9418.

This change completely removes the Git daemon service stub, its post-start execution step, related configuration environment variables (`DEVOPS_GIT_DAEMON_AUTOSTART`, `DEVOPS_GIT_DAEMON_PATHS`), port 9418 forwarding and attributes from `.devcontainer/devcontainer.json` and `devcontainer.json.j2`, and egress allowance from the Argo CD NetworkPolicy.

## Acceptance Criteria

- [x] **Daemon gone.**
  - Step 7 of post-start is deleted, along with `_git_daemon_pid_file`, `_is_git_daemon_running` and `_start_git_daemon` (`src/devops_cli/commands/devcontainer.py`). Later post-start steps are renumbered.
  - Nothing reads `DEVOPS_GIT_DAEMON_AUTOSTART` or `DEVOPS_GIT_DAEMON_PATHS`.
  - A post-start test with a recording `run_subprocess` stub asserts that no call starts with `["git", "daemon"]`, with neither variable set (`test_post_start_never_starts_git_daemon`).
- [x] **Daemon tests gone.** Tests for the daemon in `tests/test_devcontainer.py` and the five `DEVOPS_GIT_DAEMON_AUTOSTART` setenv lines are deleted.
- [x] **Devcontainer config.**
  - The template no longer sets `DEVOPS_GIT_DAEMON_AUTOSTART`. The minikube branch drops 9418 from `forwardPorts` and `portsAttributes`.
  - The non-minikube branch is removed, leaving `{% if minikube %}…{% endif %}`.
  - `.devcontainer/devcontainer.json` drops `DEVOPS_GIT_DAEMON_AUTOSTART`, `forwardPorts`, and `portsAttributes`.
  - A test renders the template with minikube on and off. Both outputs parse as JSON, and neither contains the variable or port 9418 (`test_devcontainer_template_contains_no_git_daemon`).
- [x] **Argo CD's policy.**
  - `k8s/argocd/networkpolicy.yaml` drops port 9418, and the comment drops "Git daemon 9418".
  - `tests/test_k8s_network_policies.py` asserts 443 and 22, and asserts that 9418 is absent.
- [x] **Docs.**
  - **Docstring.** The `bootstrap-gitops` docstring states what the command does (applies the GitOps root Application). Regenerated `docs/commands/argo.md` and `docs/CLI_REFERENCE.md` with `devops docs generate`, and `devops docs check` passes.
  - **DEVCONTAINER_USAGE.md.** The example drops its `forwardPorts` and `portsAttributes` block.
  - **AGENTS.md.** Drops "local git daemons" in-place.
- [x] **Nothing left.** Grep confirms no unreferenced git daemon or 9418 occurrences remain across codebase.
- [x] **Changelog.** `changelog.d/1122.md` records the removal under `### Removed`. `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.

Pending a person:
- Daemon gone: after rebuilding the devcontainer, `ss -ltn | grep -c ':9418 '` prints `0`, and `pgrep -x git-daemon` prints nothing.
- No forward: VS Code's Ports view lists no 9418.
