## Problem or Motivation

A full run of the suite on 16 workers takes 287 s, and the seconds of all tests add up to 2,423 s, which is 151 s when spread on 16 workers with no loss. The other 136 s are not in a test: they are the start of 16 workers, the collection that each of them repeats, the tail of the longest tests, and the coverage report at the end. Measured on 2026-10-27 on a 16-CPU host (11,285 tests, host idle at the start).

Two facts show that part of this is work that each worker repeats:

- Each xdist worker collects the whole suite. The issue #2356 measured 9 s for 11,282 tests in one process on an idle host, so 16 workers spend about 144 s of CPU on collection in each run.
- The seconds of a test include the first import of a heavy library on its worker. The 184 tests that rank worst by coverage density summed to 192 s in the run, and to 61 s when run one after the other in one process. The provider factory test took 5.9 s in the run and 2.7 s in the one-process run, and `test_claude_extended_thinking_payload`, a test of a payload, took 11.3 s in its call. A test that carries the import cost of its worker moves that cost to the next test when the test goes.

On the 4-CPU runner the same costs weigh more: the job `Tests & Coverage` has a median of 291 s (ADR 0014), and the workers there share 4 CPUs.

This issue is a sub-issue of #2356.

## Proposed Solution & Architectural Design

Measure first. Report CPU time (user plus system) from the host, over three runs on an idle host (`uptime` under 2 before each run), not wall time: a loaded host moved the wall time of the same suite from 3 m 28 s to 5 m 3 s and 6 m 27 s on 2026-10-27 (#2356).

1. **Split one run.** For a full run, record for each worker: the time from its start to its first test, its collection time, and its busy time. `pytest -v` with xdist prints the worker of each test (`[gw3]`), and `--durations=0` prints the seconds. Add the CPU time of the controller after the last test.
2. **Rank the first imports.** Run the suite once with `python -X importtime` on one worker, or print `sys.modules` growth per test, and list the heavy imports (`pydantic_ai`, `anthropic`, `kubernetes`, `textual`) that a test body first causes.
3. **Try the changes the numbers support**, one per pull request, each with its CPU time before and after:
   - fewer workers than CPUs on the 4-CPU runner (`-n 3`, `-n 2`);
   - importing the heavy library once in a session fixture or in `conftest.py`, so the cost is in a known place and not in a test;
   - a shorter collection (fewer imports at the top of test modules).

**Acceptance:** the pull request states the split with three-run CPU numbers, and makes the change with the largest share. The full run on an idle host is at least 5% lower in CPU time, and the median of `Tests & Coverage` on the runner does not rise.

## Target Subsystem

SDLC, Git & PR Governance

## Existing Tool Considered

- **`pytest-xdist`** is in use (`-n logical --dist worksteal`). Its `-n` and `--maxprocesses` options set the worker count.
- **`python -X importtime`** lists the cost of each import, and is already used by `tests/test_cli_startup_imports.py`.
- **`pytest --durations`** and **`pytest -v`** with xdist give the seconds and the worker of each test. Nothing new is built.


Source: https://github.com/dan-petty/devops-cli/issues/2356

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=bb46660c8d12e28520a25e8171ec300c627df0db -->
## Proposed design

### Problem statement
The full test suite on 16 xdist workers takes 287 s. Of that, 136 s is not in test execution. Each worker repeats collection and pays the first-import cost of heavy libraries. This issue measures that repeated work and applies the single change with the largest share to reduce total CPU time.

### Acceptance criteria
- Criterion 1: The pull request reports per-worker CPU time split from three runs on an idle host.
  Verification: The pull request description shows start-to-first-test, collection, and busy time for each of the 16 workers across three runs, with uptime under 2 before each run.
- Criterion 2: The pull request lists the heavy first imports ranked by cost.
  Verification: The pull request description shows a ranked list of modules first imported by a test body, with their import time in seconds, obtained via python -X importtime or sys.modules growth.
- Criterion 3: The pull request makes the change that removes the largest share of the 136 s overhead.
  Verification: The pull request description states which of the three candidate changes it applies and why that change has the largest share.
- Criterion 4: The full run on an idle host is at least 5% lower in CPU time after the change.
  Verification: Three runs before and after the change show a reduction of at least 5% in total user plus system CPU time.
- Criterion 5: The median of the Tests & Coverage job on the 4-CPU runner does not rise.
  Verification: The runner history shows the median at or below 291 s after the change merges.

### Key questions
- **Which heavy libraries does the measurement target?**: pydantic_ai, anthropic, kubernetes, and textual, as listed in CONST_CLI_HEAVY_MODULES in the startup import tests. [sources: tests/test_cli_startup_imports.py:17]
- **What is the xdist worker configuration?**: The suite runs with -n logical --dist worksteal, as recorded in the changelog for issue #1725. [sources: CHANGELOG.md:484]
- **What is the measurement methodology?**: Report CPU time (user plus system) from the host over three runs on an idle host with uptime under 2, not wall time. A loaded host moved wall time from 3 m 28 s to 6 m 27 s on the same suite. (proposed)
- **What is the acceptance threshold for the CPU time reduction?**: The full run on an idle host must be at least 5% lower in CPU time, and the median of Tests & Coverage on the 4-CPU runner must not rise above 291 s. (proposed)
- **Does this issue depend on another issue in the roadmap?**: No. This issue is a sub-issue of #2356, meaning it delivers part of #2356 rather than depending on it. It has no prerequisite issues. (proposed)

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Medium", "Owner": "Agent", "Priority": "P2-Medium", "Status": "Planned", "Value": "Medium", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "152dfb1b5f37a7684e1240939d442f690248d0d36c9e6c3307e36e67f496fe81", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "dfda10ccb40b554383291051099d4e83220f74223b2afbbd93eabe2de7cb14e7", "stage.branch": "perf/2371-measure-and-cut-what-each-of", "stage.file_cap": null, "stage.groups": "[[\"Add session fixture for heavy module imports\", 3073]]", "stage.needs_split": null, "stage.pr": "2986", "stage.ready": "2986", "stage.sha": "e675d53ff91d23706f7d85d4662d4868a2d00a26"} -->
