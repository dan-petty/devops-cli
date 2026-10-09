# Task 1384: A Sandbox Workspace Never Holds the User's SSH Agent or X11 Socket

**Issue**: [#1384](https://github.com/dan-petty/devops-cli/issues/1384)
**Status**: Done
**Milestone**: v0.2.30
**Priority**: priority/p1-high
**Scope**: type/security, scope/security

## Description

#1115 made `validate_sandbox_workspace` in `src/devops_cli/sandbox/engine.py` the one workspace
check behind `devops docker sandbox`, `devops test sandbox`, `devops sandbox deploy` and the MCP
tools `docker_sandbox` and `sandbox_deploy`. It refuses the engine socket's directory, `/run` and
`$XDG_RUNTIME_DIR`. Other user sockets that give a container the user's authority were not
covered: the SSH agent socket (`SSH_AUTH_SOCK`, for example `/tmp/ssh-*/agent.N` or VS Code's
`/tmp/vscode-ssh-auth-*.sock`) and the X11 socket directory `/tmp/.X11-unix`. A workspace of
`/tmp/ssh-XXXX` was accepted, which handed the sandbox the user's SSH agent, and `/tmp` was refused
only when `$XDG_RUNTIME_DIR` lay under it.

Now the check also refuses a workspace that is, or holds, one of these directories:
`/tmp/.X11-unix`, and, when `SSH_AUTH_SOCK` is an absolute path, the directory of that socket and
the directory the socket leads to when it is a symlink. Each is compared both as named and
resolved, so `/tmp` stays refused where `/tmp/.X11-unix` is itself a symlink, and the directory the
link leads to is refused too. The rule is one-way: VS Code's SSH-auth socket sits directly in
`/tmp`, so a workspace under the agent's directory is still mounted. An unset, empty or relative
`SSH_AUTH_SOCK` adds no rule, as #1115 treats `XDG_RUNTIME_DIR`. The check reads one environment
variable and calls `Path.resolve()`, so it makes no request.

## Key Changes

- `src/devops_cli/sandbox/engine.py`: `_user_socket_dirs()` and
  `_check_workspace_user_socket_dirs(resolved)`, which `validate_sandbox_workspace` runs after the
  #1115 socket rule. No entry point changes: all five already run the shared check.
- `src/devops_cli/config/constants.py`: `CONST_SSH_AUTH_SOCK_ENV_VAR` and `CONST_X11_SOCKET_DIR`.
- `tests/conftest.py`: the autouse `isolate_ssh_agent` unsets `SSH_AUTH_SOCK`, so no test sees the
  developer's own agent.
- `tests/test_sandbox_lifecycle.py`: each `_REFUSED_WORKSPACES` case carries the environment it
  runs under instead of a `DOCKER_HOST` value, so a case can set `SSH_AUTH_SOCK` or clear
  `XDG_RUNTIME_DIR`.

## Acceptance Criteria

- [x] **Refused paths.** `test_a_workspace_overlapping_a_socket_directory_is_refused_before_any_engine_call` (`tests/test_sandbox_lifecycle.py`), parametrised over both runners, refuses each new case before any engine call, and the client mock records no call: the `SSH_AUTH_SOCK` directory, the directory that holds it, the directory a symlinked agent socket leads to, a `tmp_path` holding a VS Code-style `vscode-ssh-auth-*.sock`, `/tmp/.X11-unix`, and `/tmp`.
- [x] **The refusal names the workspace and the protected directory** in every new case.
- [x] **Accepted paths.** `test_a_workspace_beside_the_ssh_agent_directory_is_mounted` mounts a workspace under the agent's directory with both runners, and mounts it with `SSH_AUTH_SOCK` unset, empty and relative (`agent.1`, with the workspace as the working directory).
- [x] **MCP.** With `workspace` set to the SSH agent's directory, `docker_sandbox` and `sandbox_deploy` raise `SandboxValidationError` and `_run_mcp_cmd` is not called.
- [x] **Request-free and shared.** The rule lives in `validate_sandbox_workspace`, which every entry point already runs; it reads `SSH_AUTH_SOCK` and resolves paths only.
- [x] **Release.** `changelog.d/1384.md` lists the newly refused workspaces. The tests are offline, start no container, and each call phase stays under 1 s.
- Pending a person: in a VS Code devcontainer terminal where `SSH_AUTH_SOCK` is set, on a build with this fix, run `devops docker sandbox --workspace "$(dirname "$SSH_AUTH_SOCK")" -- true` and `devops docker sandbox --workspace /tmp -- true`. Confirm that both are refused before any container is created, and record the results on the issue.
