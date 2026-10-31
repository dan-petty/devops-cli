## 1. Core Process Seam and Fakes

- [x] 1.1 Add `spawn_sandbox` and `terminate_process_group` to `ProcessRunner` and `DefaultProcessRunner` in `src/devops_cli/core/process.py`
- [x] 1.2 Implement `FakeSandboxProcess` and `spawn_sandbox` / `terminate_process_group` on `ProcessFake` in `tests/support/fakes/process.py`

## 2. Sandbox Host and Tests

- [x] 2.1 Remove `_is_mock_subprocess` and `_communicate_mock` from `src/devops_cli/sandbox/host.py`
- [x] 2.2 Wire `HostSandbox._run_sandbox_process` through `get_process_runner().spawn_sandbox`
- [x] 2.3 Write failing tests first for output cap, timeout, and reap on `process_fake` in `tests/sandbox/test_host_sandbox.py`
- [x] 2.4 Make `@pytest.mark.bwrap` tests opt-in when `-m bwrap` is specified

## 3. Tool Executor and Verification

- [x] 3.1 Migrate git starts in `tests/ai/test_tool_executor_contract.py` to use shared fakes
- [x] 3.2 Verify all tests and invariant checks pass
