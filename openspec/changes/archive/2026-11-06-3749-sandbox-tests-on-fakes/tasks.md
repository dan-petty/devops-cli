# Tasks

## 1. The span fallback leaves the sandbox command (behavior)

- [x] 1.1 Write `tests/telemetry/test_trace_span_resolution.py`: a named trace in the buffer returns its spans, an unknown trace with `last` returns the latest buffered trace, an unknown trace without `last` returns no spans, no trace id returns the latest trace, and an empty buffer returns none. The test fails on the base because the function does not exist.
  Verification: `uv run devops ci test tests/telemetry/test_trace_span_resolution.py`
- [x] 1.2 Add `resolve_trace_spans_or_latest` to `src/devops_cli/telemetry/waterfall.py`, call it from `traces` in `src/devops_cli/commands/sandbox.py`, and delete `_resolve_spans_for_traces`.
  Verification: `uv run devops ci test tests/telemetry/test_trace_span_resolution.py tests/telemetry/test_sandbox_traces.py`

## 2. The cgroup root is a parameter of the engine and the collector (behavior)

- [x] 2.1 Write the failing tests of `tests/sandbox/test_sandbox_cgroup_metrics.py` and `tests/sandbox/test_sandbox_engine.py` that read a cgroup tree under `tmp_path` through `cgroup_root`: the docker scope of a container, the previous sample threaded into the next CPU reading, and one previous sample for each engine.
  Verification: `uv run devops ci test tests/sandbox/test_sandbox_cgroup_metrics.py tests/sandbox/test_sandbox_engine.py`
- [x] 2.2 Add `cgroup_root` to `read_cgroup_v2_metrics` and `collect_sandbox_metrics` in `src/devops_cli/sandbox/metrics.py`, and to the constructor of `WorkloadSandboxEngine` in `src/devops_cli/sandbox/engine.py`. The default is the host mount `/sys/fs/cgroup`.
  Verification: `uv run devops ci test tests/sandbox/test_sandbox_cgroup_metrics.py tests/sandbox/test_sandbox_engine.py tests/sandbox/test_sandbox_metrics.py`

## 3. The incident archive is private from its creation (other)

- [x] 3.1 In `archive_incident` of `src/devops_cli/sandbox/logs.py`, create the temporary file with `os.open(..., 0o600)`, and delete the `chmod` of the file with its `SandboxError` branch. Delete `test_archive_panic_incident_chmod_failure`.
  Verification: `uv run devops ci test tests/commands/test_sandbox_logs.py`

## 4. The sandbox tests use the fakes and the public interface (other)

- [x] 4.1 Add `tests/support/sandbox.py` with the `register_sandbox` fixture, `engine_stats_frame`, `port_of` and the Prometheus servers. Give `FakeSandboxProcess` a `wait_error`. Move the socket of `docker_daemon` to a directory beside `tmp_path`.
  Verification: `uv run devops ci test tests/sandbox tests/docker tests/core/test_docker_engine.py`
- [x] 4.2 Move the host, policy-property, probe, metrics, logs, networking and lifecycle tests onto `ProcessFake`, `DockerEngineFake`, the tracer buffer, `scripted_resolver`, loopback servers, the `config` fixture and the `cli` fixture. Remove every private import, patch site (but the two seam sites), module-level `CliRunner()` and catch-all test.
  Verification: `uv run devops ci test tests/sandbox tests/commands/test_sandbox_lifecycle.py tests/commands/test_sandbox_logs.py tests/commands/test_sandbox_metrics.py tests/commands/test_sandbox_network_policy.py`
- [x] 4.3 Check that the successors of the seven files hold no private import and no `CliRunner`.
  Verification: `! git grep -n -F -e "CliRunner" -e "from unittest.mock import" -- tests/sandbox/test_sandbox_engine.py tests/sandbox/test_sandbox_metrics.py tests/sandbox/test_sandbox_models.py tests/sandbox/test_sandbox_policy.py tests/sandbox/test_sandbox_ports.py tests/sandbox/test_sandbox_registry.py tests/sandbox/test_sandbox_trace_context.py tests/sandbox/test_sandbox_workspace.py tests/commands/test_sandbox_lifecycle.py tests/commands/test_sandbox_logs.py tests/commands/test_sandbox_metrics.py`

## 5. The three large files are split by behaviour (other)

- [x] 5.1 Split `test_sandbox_lifecycle.py`, `test_sandbox_metrics.py` and `test_sandbox_networking.py` by behaviour, each move in a commit of its own, and move `tests/core/test_sandbox_policy_properties.py` to `tests/sandbox/`.
  Verification: `uv run devops ci test tests/sandbox tests/commands/test_sandbox_lifecycle.py tests/commands/test_sandbox_logs.py tests/commands/test_sandbox_metrics.py tests/commands/test_sandbox_network_policy.py`

## 6. The documents state the new fixtures (other)

- [x] 6.1 Add the `register_sandbox` fixture and the socket directory of `docker_daemon` to the Docker engine bullet of `docs/TESTING.md`.
  Verification: `uv run devops ci docs`
- [x] 6.2 Check that the change folder is valid.
  Verification: `uv run devops openspec check`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
