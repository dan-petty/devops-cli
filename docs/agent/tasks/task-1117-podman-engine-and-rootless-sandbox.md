# Task: Podman engine discovery and rootless sandbox workspace write mapping (#1117)

**Issue**: [#1117](https://github.com/dan-petty/devops-cli/issues/1117)
**Scope**: type/feature, scope/cli, scope/security, priority/p1-high
**Feasibility**: Verified Podman socket layout ($XDG_RUNTIME_DIR/podman/podman.sock, /run/podman/podman.sock), docker-py compatibility with Podman Engine API, and user namespace UID 0 mapping for rootless container write permissions.

## Description

Enables developer workstation automation and container sandbox execution on systems running Podman without requiring Docker or root privileges. Container commands locate a local Podman engine socket automatically when Docker is absent or stopped, and sandboxes map user permissions so rootless containers can write to mounted workspace trees.

- **Endpoint Resolution Precedence**:
  1. `CONTAINER_CONNECTION`: If set, fails fast with an informative error directing configuration to `CONTAINER_HOST`.
  2. `CONTAINER_HOST`: Environment variable override (with TLS options `DOCKER_TLS_VERIFY` and `DOCKER_CERT_PATH`).
  3. `DOCKER_HOST`: Traditional Docker environment variable.
  4. `DOCKER_CONTEXT`: Explicit context name from environment.
  5. Current Context: Non-default `currentContext` in `~/.docker/config.json`.
  6. Rootless Podman Socket: `$XDG_RUNTIME_DIR/podman/podman.sock` (or `/run/user/<uid>/podman/podman.sock` when unset), if the socket exists.
  7. Rootful Podman Socket: `/run/podman/podman.sock`, if the socket exists and `os.access` allows read and write.
  8. Docker Default Socket: Fallback to `/var/run/docker.sock`.
- **Default Socket Failure Message**:
  When dialling Docker's default socket fails, the error message appends `; set CONTAINER_HOST or DOCKER_HOST, or run systemctl --user enable --now podman.socket`.
- **Engine Facts & Introspection**:
  - `kind()`: Returns `"Podman"` when `version()["Components"]` contains `"Podman Engine"`, else `"Docker"`.
  - `security_options()`: Returns `info().get("SecurityOptions", [])`.
  - `is_rootless()`: Checks if `"name=rootless"` is in `security_options()`.
  - Each fact is retrieved once and memoized per `DockerEngineService` instance.
- **Sandbox User Mapping**:
  - Rootless engine: sandbox container creation passes `user="0:0"`, mapping container root to the host user to ensure workspace write access.
  - Rootful engine: passes host `f"{uid}:{gid}"`.
  - Running as root (`rootless=False` or `--root` flag): omits the `user` parameter.
  - Dry run summary displays `uid:gid` along with an informative note that a rootless engine runs as container root (the host user).
- **Streamed Container Stats**:
  - `container_stats`: reads the 2nd frame of the streamed response to capture accurate CPU and memory deltas, then closes the stream.
  - `stream_container_stats`: drops the uncalculated 1st frame before yielding samples.
- **Build Cache Adaptation**:
  - `devops docker cache` on Podman exits 1 with `"Podman keeps no BuildKit cache; its build layers are images, and `devops docker prune` removes the dangling ones."`, invoking neither `prune_builds` nor `df`.
- **Subprocess & Environment Containment**:
  - `_wait_for_docker_daemon` polls `get_engine().ping()` without calling the `docker` binary.
  - Dive scanner passes `DOCKER_HOST` in subprocess `env` when the resolved endpoint was not originally from `DOCKER_HOST`.
  - Cosign image signing and verification pass `extra_allowed_env={"XDG_RUNTIME_DIR"}` to permit user key access without polluting `DEFAULT_ALLOWED_ENV_VARS`.
  - Deleted obsolete `DEFAULT_CONTAINER_ENGINE` and `BIN_DOCKER` constants.

## Acceptance Criteria

- [x] **Precedence & Fallback**: `tests/test_docker_engine.py` validates endpoint resolution across `CONTAINER_HOST`, `DOCKER_HOST`, contexts, rootless Podman, rootful Podman (with R/W check), and Docker default.
- [x] **Configuration Errors**: `tests/test_docker_engine.py` asserts `CONTAINER_CONNECTION` raises a configuration error naming `CONTAINER_HOST` without dialling or constructing a client.
- [x] **Dial Failure Guidance**: `tests/test_docker_engine.py` asserts dial failure on the default socket appends `; set CONTAINER_HOST or DOCKER_HOST, or run systemctl --user enable --now podman.socket`.
- [x] **Engine Facts**: `tests/test_docker_engine.py` validates `kind()`, `is_rootless()`, and memoization over Engine API responses.
- [x] **Container Stats**: `tests/test_docker_engine.py` verifies single-shot stats discards the 1st frame and computes CPU percentage from the 2nd frame.
- [x] **Build Cache**: `tests/test_docker_engine.py` asserts `devops docker cache` exits 1 on Podman without calling `prune_builds` or `df`.
- [x] **Sandbox User Mapping**: `tests/test_sandbox_lifecycle.py` asserts `resolve_sandbox_user` maps to `"0:0"` on rootless engines, `uid:gid` on rootful engines, and `None` when running with `--root`.
- [x] **Subprocess Integrations**: `tests/test_devcontainer.py`, `tests/test_security_dive.py`, and `tests/test_docker_cosign.py` verify daemon polling via `get_engine().ping()`, Dive `DOCKER_HOST` propagation, and Cosign `XDG_RUNTIME_DIR` pass-through.
- [x] **Documentation**: `docs/cheatsheets/docker.md` and `src/devops_cli/ai/knowledge_base/devops_cli/libraries/docker.md` document endpoint precedence, rootless activation, and scope limits.
- [x] **Changelog Fragment**: Created `changelog.d/1117.md`.
- [x] **CI Quality Gate**: `uv run devops ci` completes with 100% passing checks.

## Decisions and deviations

- **No `DEFAULT_ALLOWED_ENV_VARS` Pollution**: `XDG_RUNTIME_DIR` is passed explicitly via `extra_allowed_env` to Cosign subprocess calls rather than being added to the global allowlist, ensuring least-privilege environment hygiene.
- **Complexity and Nesting Bounds**: `_gather_endpoint` and `_build_create_kwargs` were decomposed into dedicated single-responsibility helpers (`_podman_rootless_socket_path`, `_find_podman_socket`, `_check_container_connection`, `_with_tls`), ensuring cyclomatic complexity $M \le 8$ (within $M \le 10$) and nesting depth $< 4$.
