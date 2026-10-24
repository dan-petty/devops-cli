# Proposal

## Why

Issue #1982: `scanner_fake` doubled `shutil.which` and `subprocess.run`. The review scanners and the agent scan tools start their tools through a `ToolExecutor`, so the process edge of a scanner has a seam. The fake still patched the standard library below that seam, and docs/TESTING.md asks a test to install the fake of an edge through its seam. This is part 3 of the tracker #772.

## What Changes

- `ScannerFake` in `tests/support/fakes/scanners.py` becomes a `ToolExecutorFake`, scripted with the recorded run of each scanner. It answers a request for a scanner that it holds with the exit code, the standard output and the standard error of the run, and starts nothing.
- The `scanner_fake` fixture makes every `DirectToolExecutor` answer through the fake. It sets `run` on the class, so the executors that the global scanner registry made on import also reach the fake. A request for another tool goes on to the `run` that the fixture replaced, under the floor's refusal of a real scanner. So does the canary run of a tool, in a working directory named with `CONST_CANARY_WORKDIR_PREFIX`: the root conftest answers it with the recorded canary output, so the canary of a scanner that the fake holds still passes.
- The fake puts an executable stand-in for each scanner that it answers in `bin_dir`, and the fixture puts `bin_dir` first on PATH. The fake patches no `shutil` or `subprocess` name.
- `ToolExecutorFake` takes `require_commit` and `require_files`, which it gives to `record_tool_run`. The default records as the sandbox executor does. With both false, the fake records as the direct executor does, and `ScannerFake` uses that mode.
- A test scripts another answer for a scanner with `ScannerFake.script(tool, ToolAnswer(...))`, in place of a write to `scanner_fake.recorded`. The tests of the agent scan tools in `tests/test_builtin_tools.py` use it.
- `tests/test_tool_executor_contract.py` runs the two cases of a record that the direct executor cannot complete over the direct executor and over the fake in its direct mode.
- `tests/test_scanner_contract.py` keeps the recordings and the adapter cases. Its third case checks the stand-ins on PATH, the answer of the fake through `DirectToolExecutor`, and a start of git through the direct executor. A new case checks that the canary of Semgrep, Bandit, kube-linter and Pluto gets the recorded canary answer when the fake holds an answer for the tool. Gitleaks and osv-scanner have no canary.
- docs/TESTING.md, the docstring of `tests/support/fakes/openspec.py` and the docstring of `tests/test_scanner_tool_executor.py` describe the new fake.

The change alters no behavior that a consumer observes. It changes only test fakes, tests and docs/TESTING.md, and no file under `src/`. So it has no spec delta, and `.openspec.yaml` sets `skip_specs: true`.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `tests/support/fakes/scanners.py`: the fake over `ToolExecutorFake`, the stand-ins on PATH, and the fixture on `DirectToolExecutor.run`.
- `tests/support/fakes/tool_executor.py`: `require_commit` and `require_files`.
- `tests/test_tool_executor_contract.py`, `tests/test_scanner_contract.py`: the contract cases.
- `tests/test_builtin_tools.py`: the scripted answers through `script`.
- `docs/TESTING.md`, `tests/support/fakes/openspec.py`, `tests/test_scanner_tool_executor.py`: the text that described the old fake.

## Feasibility

I confirmed the premise against the code at main 02fee43a:

- `BaseSecurityScanner._run_tool` in `src/devops_cli/security/base.py` is the only place under `src/` that makes a `ToolRequest` (`grep -rn 'ToolRequest(' src`). A scanner that gets no executor makes a `DirectToolExecutor`, and so does the review orchestrator.
- #1435 moved the agent scan tools for Trivy, kube-linter, Pluto, Bandit, Gitleaks and Semgrep onto the adapters. `scan_popeye` and `scan_uv_audit` still run their own command lines (#1434, #2106). No test reaches them through `scanner_fake`: `tests/test_builtin_tools.py` patches `_run_tool_cmd` for them.
- The global scanner registry makes its scanners, and their executors, on import (`src/devops_cli/security/registry.py`). A fixture that replaced only the name `DirectToolExecutor` left four registry tests of `tests/test_security_semgrep.py` on the real executor, and the floor refused Semgrep. So the fixture sets `run` on the class.
- A fake in the default mode of `ToolExecutorFake` refuses a checkout that git cannot read. With it, `tests/test_scanner_tool_executor.py::test_a_scan_of_a_checkout_that_git_cannot_read_still_runs` failed with status `failed` in place of `ran`. The fake that stands in for the direct executor must record as the direct executor does.
- Since #1978, a review runs the canary of each tool on its tool executor, and `pin_review_tool_canaries` in the root conftest answers a canary run of `DirectToolExecutor` with the recorded output. A fake that answered every request for its scanners also answered the canary runs of Semgrep and Bandit. Four review tests then failed: two in `tests/test_review_security_tools.py` and two in `tests/test_review_static_analyzers.py`. So the fixture passes a canary run on.
- With the new fake, the test files that use `scanner_fake`, both contract suites, `tests/test_review_canary.py` and `tests/test_review_tool_runs.py` passed (`uv run devops ci test`).

## Existing Tool Considered

`ToolExecutorFake` (`tests/support/fakes/tool_executor.py`) is the shared fake of the review-tool edge (ADR 0007). This change builds `scanner_fake` on it and adds no second fake. The pytest `monkeypatch` fixture installs it. The change deletes the stdlib doubles of `ScannerFake`: its `which` and `run` methods and their patches of `shutil.which` and `subprocess.run`.
