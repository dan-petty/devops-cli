# Proposal

## Why

Issue #2542, part 1 of #1332: the security scanners looked for test mocks in product code. AGENTS.md rule 2 forbids product code that detects tests.

Measured on origin/main 1244cbfd:

- `security/base.py` imported `unittest.mock.NonCallableMock`. `_is_mocked` and `_patched_run_subprocess` searched `sys.modules` for a patched `is_dry_run`, `check_binary` or `run_subprocess`. `BaseSecurityScanner._is_dry_run`, `_check_binary` and `_run_tool` then called the patched function in place of the real one, and `_check_binary` said a program was installed whenever a test had patched `run_subprocess`.
- Seven scanner modules re-imported `run_subprocess` or `is_dry_run` with `# noqa: F401` only to be patch targets, and `tflint.py` re-imported `shutil` the same way: `bandit`, `gitleaks`, `kubelinter`, `pluto`, `popeye`, `semgrep` and `tflint`.
- 64 patch sites in 12 test files relied on that: 62 patched `run_subprocess`, `is_dry_run`, `check_binary` or `shutil` on `security.base` or on one of the seven modules. One patched `zizmor.run_subprocess`, which `_patched_run_subprocess` also found, and one patched `golangci_lint.check_binary`, which `_is_mocked` found in the scanner's own module.

## What Changes

- `security/base.py` loses the `NonCallableMock` import, `_is_mocked`, `_patched_run_subprocess` and the mock-aware branches. `_is_dry_run` asks `dry_run.state.is_dry_run()`, `_check_binary` asks `check_binary()`, and `_run_tool` always starts the tool through the scanner's tool executor.
- The `# noqa: F401` re-imports in the seven scanner modules are deleted.
- The 64 patch sites move onto the merged fakes:
  - `scanner_fake` (#1666) answers each tool run and puts the program on PATH. A test that ran a scanner with a patched `run_subprocess` scripts the tool's answer instead.
  - A missing program is a PATH that does not hold it.
  - Dry-run mode is set through `set_dry_run`, which the suite resets after each test.
- `ToolExecutorFake` (#772) and `ScannerFake` gain two methods:
  - `fail(tool, error)` raises `error` from each run of `tool`, as an executor that cannot start the tool raises.
  - `answer_with(tool, responder)` answers each run with what `responder` gives for the request, for a tool whose output depends on its arguments and on the files it reads.
- No behavior that a consumer observes changes: the deleted paths ran only under a test mock. So the change has no spec delta and sets `skip_specs: true`.
- This change fits one pull request.

## Impact

- `src/devops_cli/security/base.py`, `bandit.py`, `gitleaks.py`, `kubelinter.py`, `pluto.py`, `popeye.py`, `semgrep.py`, `tflint.py`.
- `tests/support/fakes/tool_executor.py`, `tests/support/fakes/scanners.py`.
- The tests: `test_consolidation_security_scanner_base.py`, `test_security_bandit.py`, `test_security_gitleaks.py`, `test_security_semgrep.py`, `test_tflint.py`, `test_secops.py`, `test_scan_outcomes_and_gating.py`, `test_security_sarif.py`, `test_golangci_lint_scanner.py`, `test_security_zizmor.py`, and #1328's `test_review_untrusted_tree.py` and `test_review_static_analyzers.py` (the 2026-10-07 decision on #1332 lets this item edit them).

## Feasibility

- The fakes are on main: `tests/support/fakes/tool_executor.py` (#772) and `tests/support/fakes/scanners.py` (#1666, #1982). `scanner_fake` patches `run` on `DirectToolExecutor` and `SandboxToolExecutor`, so a scanner from the global registry also reaches it.
- Both executors start a tool with `input=""` (`security/tool_executor.py:530`, `:660`). One rewritten test asserted the `input=""` that only the patched function received; that check now belongs to the executor.
- A test that patched `run_subprocess` on `security.base` had every scanner "installed" through `_check_binary`. On the fake, `answer_with` and `script` put each program the test uses on PATH. One review test also needs pluto scripted, because the patched function had answered pluto too.
- A timed-out `ToolResult` must carry the timeout exit code, so a timeout is `ToolAnswer(exit_code=CONST_SANDBOX_TIMEOUT_EXIT_CODE, timed_out=True)`. The timeout reason then names the timeout the scan gave, `DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS`, and the test of a timeout that quotes no command now builds the command with the secrets in it.
- #1332's other dependencies are not all on main (#1313, #1314, #1317, #1318, #1319). This part uses none of them; #2543, #2544 and #2545 carry the rest of #1332.
- `ai/review/pipeline.py:657` keeps its own `NonCallableMock` check. It belongs to #1328.

## Existing Tool Considered

The change builds no tool. It deletes the mock detection and uses the fakes that exist. The two fake methods follow the `fail` of the Docker engine fake (#2534) and the scripted answers that `ToolExecutorFake` already has.
