# Proposal

## Why

Seven sandbox test files reach `sandbox/` through patches and private names (#3749, part 4 of 6 of #1335). Measured on `origin/main` (44d9196d) with the counting rules of #1335, they hold 70 patch sites, 28 private imports, 267 tests, 16 `CliRunner()` calls and a catch-all test. The patches replace `WorkloadSandboxEngine`, the registry, metrics functions, `trace_span`, `probe_tcp`, the telemetry settings and the console objects. A test that patches an internal name pins how the code is wired and not what it does. The Docker, process and OTLP fakes and the real registry already give the same answers through the public interface.

The span fallback in `commands/sandbox.py` (`_resolve_spans_for_traces`) is domain logic. It has nothing that is specific to the sandbox, and a test can reach it only through the command.

## What Changes

- `telemetry/waterfall.py` gets the public function `resolve_trace_spans_or_latest`. `commands/sandbox.py` calls it, and `_resolve_spans_for_traces` is gone. A new test in `tests/telemetry/` holds the three cases of the rule.
- The seven test files use no patch site except the two seam sites that #1314 replaces (`socket.getaddrinfo` in the `failed_lookups` fixture and `socket.socket` in the TCP timeout test). They hold no private import, no module-level `CliRunner()` and no catch-all test.
  - A sandbox that `devops sandbox deploy` leaves is now one fixture, `register_sandbox` in `tests/support/sandbox.py`: a record in the registry of the test and a container in `DockerEngineFake`. The command and engine tests use it with the `cli` fixture.
  - Spans are read from the tracer buffer, and the telemetry settings are set with the `config` fixture.
  - DNS answers come from `scripted_resolver` and `public_dns`, and HTTP answers from loopback servers that the tests start.
- `WorkloadSandboxEngine` and `collect_sandbox_metrics` take a `cgroup_root`, and `read_cgroup_v2_metrics` looks for the cgroup of a container below it. The default is `/sys/fs/cgroup`, so no command changes. A test builds a cgroup tree under `tmp_path`.
- `archive_incident` creates its file with mode `0o600` through `os.open`. It no longer calls `chmod` on the file, and it no longer holds the `SandboxError` branch for a failed `chmod`. No filesystem of a test can fail that call, so no public path reaches the branch. The file mode is the same as before.
- `docker_daemon` puts its socket in a directory beside `tmp_path`, so a workspace under `tmp_path` does not overlap the engine socket directory.
- The three large files are split by behaviour: `test_sandbox_lifecycle.py` into models, ports, registry, workspace, engine, policy, trace context and the lifecycle commands; `test_sandbox_metrics.py` into cgroup, Prometheus, thresholds, collection and the command; `test_sandbox_networking.py` into network config and network policy. `tests/core/test_sandbox_policy_properties.py` moves to `tests/sandbox/`.
- The change alters no behavior that a consumer observes: the commands print what they printed, and the only new code is a moved function, an optional parameter and a file-creation call with the same result. So it has no spec delta and sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Source: `src/devops_cli/telemetry/waterfall.py`, `src/devops_cli/commands/sandbox.py`, `src/devops_cli/sandbox/metrics.py`, `src/devops_cli/sandbox/engine.py`, `src/devops_cli/sandbox/logs.py`.
- Tests: the seven files of the issue and the files that they split into, `tests/telemetry/test_trace_span_resolution.py`, `tests/support/sandbox.py`, `tests/support/fakes/process.py` (`wait_error` of `FakeSandboxProcess`) and `tests/support/fakes/docker_engine.py` (the socket directory of `docker_daemon`).
- Documents: `docs/TESTING.md`.

Counts before and after, by an AST scan of the seven files and their successors:

| | Before | After |
| :--- | :--- | :--- |
| Patch sites | 70 | 2 (both seam sites) |
| Private imports | 28 | 0 |
| Module-level `CliRunner()` | 4 | 0 |
| Test functions | 267 | 283 |

Deleted tests and the code they covered:

- `test_terminate_process_group_guards_devcontainer` in `test_host_sandbox.py`. It covered the guards of the thin `_terminate_process_group` wrapper in `sandbox/host.py`. The same guards are tested at their source in `tests/core/test_process.py::test_terminate_process_group_guards_and_lifecycle`.
- `test_an_entry_that_resolves_to_no_address_adds_no_rule` in the networking tests. It covered `_build_whitelist_egress` with a stub resolver. `test_a_loopback_entry_opens_no_egress_rule` shows the same rule through `to_k8s_network_policy`.
- `test_archive_panic_incident_chmod_failure`. It covered the failed-`chmod` branch of `archive_incident`, which is gone.

## Feasibility

- The counts of the issue hold on `origin/main` (44d9196d). An AST scan of the seven files gave 70 patch sites (11 seam sites), 28 private imports and 267 test functions, as the issue states.
- The fakes exist and answer the calls that the sandbox makes. `DockerEngineFake` serves `containers.create`, `get`, `start`, `stats`, `exec_run`, the log read and `api.stop`. `uv run pytest` on the migrated files passes.
- `_resolve_spans_for_traces` in `commands/sandbox.py` held a `not trace_id` clause. `resolve_trace_spans` already returns the latest buffered trace when no id is given, so only the `last` clause with an unknown id changes the result. The moved function keeps only the `last` clause, and the new tests show the three cases of the issue.
- Two rules cannot be reached through the public interface of the sandbox on a host with `/sys/fs/cgroup`. The cgroup of a container lived under a fixed `/sys/fs/cgroup`, so a test could not feed it. The `cgroup_root` parameter fixes that, the same way the `registry` parameter of the engine does. The failed-`chmod` branch of `archive_incident` could not fail on any test filesystem; creating the file with mode `0o600` removes the need for it.
- A public IPv6 CIDR whitelist entry is refused by the validator as "private". The CIDR branch of `_resolve_public_host` is reachable only through `SandboxNetworkConfig.model_construct`, which skips the validators, and the tests use that. The defect has its own issue (#3776), and this change does not fix it.
- The row of the `Open File Descriptors` in `devops sandbox metrics` is fed by a cgroup tree that only a host path can give through the command. The `parse_cgroup_v2_directory` test keeps the count.

## Existing Tool Considered

The fakes and `pytest` fixtures of the repository cover the need: `DockerEngineFake`, `ProcessFake`, `FakeCollector`, `scripted_resolver` and the `cli`, `config` and `tracer` fixtures. No new tool is needed. The new test code is one fixture (`register_sandbox`) and the shared Prometheus servers, which replace patches in 14 files. The estimated cost is about 450,000 tokens to build, about 20,000 tokens a year to keep, and about 3 days of elapsed time, as the issue states. The change deletes the three tests listed above and the failed-`chmod` branch of `archive_incident`.

The change fits one pull request: it edits test files and five small source files, and a reviewer can read the moves as their own commits.
