# Design

## Context

A security scanner of devops-cli builds the command of its tool and hands it to a `ToolExecutor` as a `ToolRequest`. A scanner that nobody gives an executor makes a `DirectToolExecutor`, which starts the tool through `run_subprocess`. `ToolExecutorFake` is the shared fake of this seam, with its contract suite. `scanner_fake` answered the scanners below the seam, with patches of `shutil.which` and `subprocess.run`. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- `scanner_fake` answers the scanners through `ToolExecutorFake` and patches no `shutil` or `subprocess` name.
- Every test that uses `scanner_fake` passes with the same recordings.
- The contract suites hold the fake to the adapters and to the direct executor.

**Non-Goals:**

- The executor of `scan_popeye` and `scan_uv_audit` (#1434, #2106).
- The sandbox as the default executor (#772, part 4).

## Decisions

- **The fixture sets `DirectToolExecutor.run` on the class.** The global scanner registry makes its executors on import, before any fixture runs. Rejected: a replacement of the name `DirectToolExecutor` in its module. Four registry tests in `tests/test_security_semgrep.py` then reached the real executor, and the floor refused Semgrep. Rejected: a default-executor function in `src/devops_cli/security/tool_executor.py` that a test replaces. docs/TESTING.md refuses a module shaped for a test patch.
- **The fake records as the direct executor does.** `ToolExecutorFake` takes `require_commit` and `require_files` and gives them to `record_tool_run`, as `DirectToolExecutor` does. The contract suite runs the two cases of an incomplete record over both. Rejected: the default mode of the fake. It refuses a checkout that git cannot read, and the scan of such a checkout failed in a test where the direct executor runs it.
- **A scanner is installed through a stand-in on PATH.** `ScannerFake.script` writes an executable stand-in in `bin_dir`, and the fixture puts `bin_dir` first on PATH. The real `shutil.which` finds it. A test that sets PATH without `bin_dir` has no scanner installed, as on a host without it. Rejected: a patch of `shutil.which`, which the issue removes.
- **A request for another tool goes on to the `run` that the fixture replaced.** The fixture answers a tool that the fake holds and passes every other request to the `run` of `DirectToolExecutor` that was there before it. Git runs, and the floor refuses a real scanner, as before. Rejected: a fake that fails every other request. The autouse fixture `pin_review_tool_canaries` installs a wrapper of `DirectToolExecutor.run` before `scanner_fake`, and that wrapper would then lose its requests.
- **A canary run goes on to the canary answers.** A review runs the canary of a tool in a working directory named with `CONST_CANARY_WORKDIR_PREFIX`, as `pin_review_tool_canaries` reads it. The fixture passes such a run on, also for a scanner that the fake holds, so the canary reads the recorded canary output. Rejected: the scan recording as the answer of a canary run. The canary of Semgrep and Bandit then failed, and four review tests failed with it.
- **A test scripts a scanner through `script`.** The tests of the agent scan tools wrote a `RecordedScannerRun` into `scanner_fake.recorded`, which the old fake read at each call. They call `scanner_fake.script(tool, ToolAnswer(...))` now, the method of the shared fake. `recorded` holds only the recordings, which the contract suite reads.
- **`runs` keeps its shape.** Each `ScannerRun` holds the command that the direct executor starts, the `program` of the request, else its `tool`, then its arguments, and the directory it starts in, `cwd` or else `workdir`. The tests that read `runs` stay as they are. A scanner hands the executor its whole command, so no argument is the `{targets}` placeholder.
