# Tasks

## 1. Repair the bwrap contract suite

Kind: test-only edit. Changes: `tests/ai/test_tool_executor_contract.py`, `src/devops_cli/roadmap/runner_tools.py`.

- [x] 1.1 `_running` reads the process table of the host with `ps`, and its two tests carry `@pytest.mark.live("ps")`. `NOT_IN_RUNNER` names `ps`.
  - Verification: `$ uv run pytest -m bwrap -n 0 tests/sandbox/test_host_sandbox.py tests/ai/test_tool_executor_contract.py`

## 2. The bwrap row of devops ci

Kind: behavior. Changes: `src/devops_cli/commands/ci.py`, `src/devops_cli/ci/cache.py`, `src/devops_cli/security/tool_executor.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/runner_tools.py`, `tests/support/ci_root.py`.

- [x] 2.1 Write the tests first: the row runs `pytest -m bwrap -n 0` over the two suites with a bound for each test that is shorter than the limit of the gate step of `Static Analysis`, starts them after the host check passes, skips with the cause and starts nothing when bubblewrap cannot make a sandbox, and a cached verdict keeps the skip.
  - Verification: `$ uv run devops ci test tests/commands/test_ci_bwrap_row.py`
- [x] 2.2 Add `CheckSpec.host_refusal`, `CheckResult.skipped` and `CICachedCheck.skipped`, the public `SandboxToolExecutor.host_refusal()`, and the `bwrap` row with `--timeout=60`. `sandbox_host` gives the gate tests stand-ins for bubblewrap and prlimit, and `RUNNER_TOOLS` names the row as a reason for pytest.
  - Verification: `$ uv run devops ci test tests/commands/test_ci_bwrap_row.py tests/commands/test_ci.py tests/commands/test_ci_shard.py tests/ci/test_ci_gate_admission.py tests/sandbox/test_sandbox_tool_executor.py tests/roadmap/test_roadmap_runner_tools.py`

## 3. Documents

- [x] 3.1 Correct the text of the `bwrap` marker in `pyproject.toml`, and state in `docs/TESTING.md`, `docs/SDLC.md` and ADR 0007 that the `bwrap` row runs the suite where the host can make the sandbox and skips with the cause elsewhere.
  - Verification: `$ uv run devops ci --check --only docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
