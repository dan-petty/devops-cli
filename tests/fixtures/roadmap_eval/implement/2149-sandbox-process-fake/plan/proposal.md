# Proposal: Sandbox Process Fake and Opt-In Bubblewrap Suite

## Why

Issue #2149 addresses the host sandbox process execution and test architecture:
1. Product code in `src/devops_cli/sandbox/host.py` contains mock detection functions `_is_mock_subprocess` and `_communicate_mock`. When a test provides a non-standard subprocess or mock, the bounded I/O loop is bypassed entirely. This violates the architectural rule that product code contains no test accommodations.
2. The bounded I/O loop in `sandbox/host.py` (`_drain_ready_channel`, `_run_selector_loop`, `_reap_sandbox_process`, `_build_bounded_result`) never executes in CI, leaving `sandbox/host.py` at 69% coverage.
3. Tests carrying the `@pytest.mark.bwrap` marker run in the devcontainer (where `bwrap` is installed) but skip on standard GitHub Actions CI runners, creating an environment divergence. ADR 0007 as amended by #2143 specifies that live bubblewrap tests must be an opt-in contract suite selected with `-m bwrap` and that default test runs on both CI and devcontainer report the same test count.
4. Direct-executor contract cases in `tests/ai/test_tool_executor_contract.py` start real `git` processes via `subprocess.run` instead of using the shared fakes.

## What Changes

- Add `spawn_sandbox` and `terminate_process_group` to the `ProcessRunner` protocol in `src/devops_cli/core/process.py`, implemented by `DefaultProcessRunner` and `ProcessFake`.
- In `src/devops_cli/sandbox/host.py`, route sandbox process spawning through `get_process_runner().spawn_sandbox(cmd)` instead of direct `subprocess.Popen`.
- Remove `_is_mock_subprocess` and `_communicate_mock` from `src/devops_cli/sandbox/host.py`.
- Add `FakeSandboxProcess` in `tests/support/fakes/process.py` featuring real OS pipes for stdout and stderr, recording signal termination and process wait calls without starting child processes.
- Add tests in `tests/sandbox/test_host_sandbox.py` covering:
  - Output cap breach terminating the process group with `SIGKILL` and reporting the byte cap.
  - Deadline expiration terminating the process group with `SIGKILL` and reporting timeout.
  - Process not exiting immediately being reaped with `SIGKILL` and a follow-up wait.
- Update `test_host_sandbox_handles_namespace_refusal` and `test_host_sandbox_reports_a_timeout_apart_from_a_failure` to use `FakeSandboxProcess` via `process_fake` instead of patching `subprocess.Popen`.
- In `tests/conftest.py`, configure `pytest_collection_modifyitems` to deselect `@pytest.mark.bwrap` tests unless `"bwrap"` is in `config.getoption("-m")`.
- In `tests/ai/test_tool_executor_contract.py`, migrate git interactions in `scenario` and `DirectToolExecutor` tests to use the shared git fake / process fake.
- Verify `uv run devops ci` passes and coverage of `sandbox/host.py` increases above 69%.

## Feasibility

- `os.pipe()` provides genuine OS file descriptors compatible with `selectors.DefaultSelector` and non-blocking reads.
- `ProcessRunner` is the single source of truth for process dispatch in `core/process.py`.
- `tests/support/fakes/git.py` and `tests/support/fakes/process.py` are already established and tested in PR #2146 and #2180.

## Existing Tool Considered

- `ProcessRunner` and `ProcessFake` already manage system processes; extending them to support `spawn_sandbox` and `terminate_process_group` avoids introducing new ad-hoc fixtures or monkeypatching.
- Standard pytest `pytest_collection_modifyitems` and `pytest_deselected` hooks cleanly deselect opt-in test categories.
