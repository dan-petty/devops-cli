# Task 1115: A Sandbox Workspace Never Exposes the Engine Socket or the Runtime Directory

**Issue**: [#1115](https://github.com/dan-petty/devops-cli/issues/1115)
**Status**: Done
**Milestone**: v0.2.29
**Priority**: priority/p1-high
**Scope**: type/security, scope/security

## Description

Three commands mount a host directory as a sandbox's `/workspace`: `devops docker sandbox` and
`devops test sandbox` through `WorkloadSandboxRunner`, and `devops sandbox deploy` through
`WorkloadSandboxEngine`. The MCP tools `docker_sandbox` and `sandbox_deploy` run them with a
workspace the MCP client chooses. The two workspace checks differed. Neither protected `/run` or
`$XDG_RUNTIME_DIR`, and both stood in for an engine-socket check by looking for the text
`docker.sock` in the path. A workspace of `/run/user/<uid>` handed the sandbox the user's session
bus, gpg-agent and keyring sockets, and a read-only bind mount still allows `connect()`.

Now `validate_sandbox_workspace` in `src/devops_cli/sandbox/engine.py` is the one check. It runs
the traversal, symlink, system-directory, home and credential-directory rules, then refuses a
workspace that is, holds or sits under a directory holding engine or session sockets: `/run`,
`$XDG_RUNTIME_DIR` when absolute, and the directory of the engine client's unix socket. Paths are
compared with `Path.resolve()` and `Path.is_relative_to`.

The socket comes from the engine's own endpoint step without the egress check, so a dry run makes
no request. `DockerEngineService.configured_host()` reads `DOCKER_HOST` or the default socket.
`resolve_host()` keeps the egress check for `client()`. The check follows the socket that
`DOCKER_HOST`, or the default, names: `unix_socket_path()` derives it with docker-py's `parse_host`
and `UnixHTTPAdapter`, so `unix://tmp/engine/docker.sock` reads as `/tmp/engine/docker.sock`, as
docker-py reads it. Docker contexts are followed once #1108 lands. When the socket file is a
symlink, as Docker Desktop's WSL integration makes `/var/run/docker.sock`, the directory the link
leads to is protected as well as the one that holds the link. An endpoint docker-py cannot parse,
such as `fd://` or `tcp://host:abc`, is refused as a `SandboxValidationError`.

## Key Changes

- `src/devops_cli/docker/engine.py`: `configured_host()` and `unix_socket_path()`; `resolve_host()`
  builds on `configured_host()`. docker-py is imported lazily, as `client()` does.
- `src/devops_cli/sandbox/engine.py`: `validate_sandbox_workspace(workspace, *, exclude_home_dir)`,
  used by `WorkloadSandboxEngine.validate_workspace_dir`. The `docker.sock` substring test and the
  `_FORBIDDEN_ROOTS` list, which `is_forbidden_system_path` already covered, are gone.
- `src/devops_cli/docker/sandbox.py`: `_validate_workspace_dir` calls the shared check and
  re-raises its refusal as `DockerSandboxError`. The duplicated root list, home check and
  substring test are gone.
- `src/devops_cli/ai/mcp/server.py`: `docker_sandbox` and `sandbox_deploy` run the shared check on
  `workspace` before building the command line, with `sandbox.exclude_home_dir` from the settings.
  The imports are lazy, so the server's import time is unchanged.
- `src/devops_cli/config/constants.py`: `CONST_SANDBOX_RUNTIME_ROOT`, `CONST_XDG_RUNTIME_DIR_ENV_VAR`
  and `CONST_DOCKER_UNIX_ADAPTER_SCHEME`. `CONST_FORBIDDEN_SYSTEM_DIRS` is unchanged.
- `tests/conftest.py`: `isolate_session_bus` points `XDG_RUNTIME_DIR` at
  `tmp_path_factory.mktemp("run")`, beside `tmp_path`, and the autouse `isolate_docker_host`
  unsets `DOCKER_HOST`.

## Acceptance Criteria

- [x] **One check.** The three commands validate the workspace through `validate_sandbox_workspace`. `devops docker sandbox` and `devops test sandbox` still raise `DockerSandboxError`, and `devops sandbox deploy` still raises `SandboxValidationError`.
- [x] **Refused paths.** `test_a_workspace_overlapping_a_socket_directory_is_refused_before_any_engine_call` (`tests/test_sandbox_lifecycle.py`), parametrised over both runners, refuses each case before any engine call, and the client mock records no call. The cases are `/run`, `/run/user/1000`, `/run/user/1000/gnupg` and `/var/run`; `XDG_RUNTIME_DIR` itself, a directory under it and the directory that holds it; the `DOCKER_HOST` socket directory, a directory under it and the directory that holds it, in both the `unix:///abs` and the `unix://rel` form; the directory a symlinked `DOCKER_HOST` socket leads to; `fd://` and `tcp://host:abc`; and `/etc/ssl`.
- [x] **Accepted paths.** A `tmp_path` workspace is mounted by both runners with `DOCKER_HOST` unset and with `DOCKER_HOST=tcp://192.0.2.1:2375`.
- [x] **The refusal names the workspace and the protected directory.** This holds for every runtime-directory and socket-directory refusal. `/var/run` is refused by the symlink rule and `/etc/ssl` by the system-directory rule, and each of those messages names the workspace.
- [x] **MCP.** With `workspace="/run/user/1000"`, or with `DOCKER_HOST` set to `fd://` or `tcp://host:abc`, each tool raises `SandboxValidationError` and `_run_mcp_cmd` is not called.
- [x] **No substring test is left.** `rg -n 'docker\.sock' src/devops_cli/docker/sandbox.py src/devops_cli/sandbox/engine.py` prints nothing.
- [x] **The shared constant is unchanged.** `CONST_FORBIDDEN_SYSTEM_DIRS` keeps its entries, and `run_subprocess(["pwd"], cwd=Path("/run"))` still runs (`tests/test_process.py`).
- [x] **Dry run makes no request.** `devops sandbox deploy --dry-run` with `DOCKER_HOST=tcp://example.com:2375` and private networks disallowed exits 0 without a host lookup.
- [x] **Test isolation.** The two `docker.sock` substring blocks (`tests/test_sandbox_lifecycle.py`, `tests/test_security_sandbox_and_protection.py`) now refuse the workspace that holds the `DOCKER_HOST` socket. The two MCP tests that used the default workspace `.` pass `workspace=str(tmp_path)`, because a GitHub runner's checkout lies under `/home`. Every other sandbox and MCP test passes unchanged.
- [x] **Release.** `changelog.d/1115.md` lists the workspaces that are now refused. The tests are offline, start no container, build no real `DockerClient` and each run well under 1 s.
- Not done here: a socket chosen through a Docker context. The check follows the socket `DOCKER_HOST`, or the default, names; #1108 extends `configured_host()` to Docker contexts, and the check follows it then.
- Pending a person: in the devcontainer, on a build that includes this fix, run `devops docker sandbox --workspace /run/user/$(id -u) -- true`, then `devops docker sandbox --workspace "$XDG_RUNTIME_DIR" -- true`, and the MCP `docker_sandbox` tool with `workspace` set to `/run/user/<uid>`. Confirm that each is refused before any container is created, and record the results on the issue.
- Pending a person: for the record, on the release before this fix, run a sandbox with workspace `/run/user/$(id -u)` and the command `python3 -c 'import socket; socket.socket(socket.AF_UNIX).connect("/workspace/bus")'`. Record on the issue whether the connect succeeds. It only connects and sends no bus message.
