# Design

## Context

The test row of `devops ci` runs `pytest --durations=N --cov=src --cov-report=term-missing --cov-report=xml` on 16 workers (`-n logical --dist worksteal`). The CI job `Tests & Coverage` runs the same row, then the step `Changed-Line Coverage`. Until now that step only reported. The floor was `fail_under = 90`. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**
- Lower the floor of the whole tree to 85% and fail a pull request that covers under 90% of its changed lines.
- Record what the suite costs and where, with a method that anyone can repeat.
- Decide from that record whether to remove tests.

**Non-Goals:**
- Removing a test (decision 2).
- The speed-ups of step 4 of the issue. They are sub-issues.
- Measuring branches in the gate (#2163). The branch figure is recorded here so the owner can decide.

## Measurement

The base commit is `main` on 2026-10-27. The host has 16 CPUs and was idle when the first run started (load average 0.5). The suite has 11,285 tests, and all passed in every run.

**Method.** Two full runs, then a join:

1. `uv run pytest --durations=0 --cov=src --cov-report=term-missing --cov-report=xml` gives the seconds of each test for `setup`, `call` and `teardown`.
2. `COVERAGE_CORE=ctrace uv run pytest --durations=0 --cov=src --cov-branch --cov-context=test --cov-report=json:<file>` gives the lines that each test runs. The `ctrace` core is needed: the default `sysmon` core of Python 3.14 does not support contexts (`core/coverage_index.py`).
3. The join reads `executed_lines` from the JSON report, so the lines are the statements that `coverage report` counts, and `CoverageData.contexts_by_lineno` for the tests that ran each line. A context is the part of its name before `|`.
4. A greedy pass removes, again and again, the test with the most seconds for each line that its removal newly loses. A line is lost when every test that runs it is removed. A line with no context ran at import and is never lost.

**Result.**

| Quantity | Value |
| :--- | :--- |
| Line coverage | 93.01% (79,649 of 85,639 statements) |
| Coverage with branches | 90.75% (79,649 lines and 19,776 of 23,918 branches) |
| Time of pytest, gate row | 287 s (299 s wall) |
| Sum of the seconds of all tests | 2,423 s: 582 s `setup`, 1,809 s `call`, 32 s `teardown` |
| Same sum, packed with no loss on 16 workers | 151 s |
| Slowest 10, 100, 500 tests | 156 s (6%), 616 s (25%), 1,280 s (53%) |
| Lines with no context (they ran at import) | 26,506 of 79,649 (33%) |
| Tests with no line that no other test runs | 8,788 of 11,285 (78%), with 1,804 s (74%) |
| Time in tests that may not be removed | 2,007 s (83%), in 8,651 tests |
| Time in tests that may be removed | 416 s (17%), in 2,634 tests |

The seconds with the most weight are in `tests/test_cli_startup_imports.py` (204 s), `tests/test_ui_reactive.py` (124 s) and `tests/test_architectural_invariants.py` (119 s). The other 136 s of the 287 s are not the time of a test: they are the start of the workers, the collection, the tail of the longest tests, and the coverage report.

**What may not be removed.** The issue forbids the removal of an invariant, a ratchet, a contract suite, a security test, a test that pins a scenario of an OpenSpec spec, and the only test of a module. No file links a scenario to a test, so the join treats as protected every file that a name rule or an OpenSpec document names: file names with `invariant`, `ratchet`, `contract`, `independence`, `startup_imports`, `tripwire`, `all_commands`, `security`, `secret`, `egress`, `ssrf`, `sandbox`, `injection`, `redact` or `snapshot`, and the 293 of 501 test files that an OpenSpec spec or change cites. This is wider than the rule: it errs on the side of keeping a test.

## Decisions

### 1. The floor is 85% and the changed lines are gated at 90%

The owner decided this on 2026-10-27 (the comment on #2356). The step `Changed-Line Coverage` runs `diff-cover` with `--fail-under 90`.

- **The floor alone is rejected.** A pull request that changes 50 lines moves the whole-tree figure by 0.06 points at most. A floor does not see it, and a floor 8 points under the figure lets untested code in.
- **An advisory report is rejected.** It has been the state since #850. A figure that fails nothing does not stop an uncovered line.
- **A gate at the floor (85%) is rejected.** A changed line is the cheapest line to test: its author has the code and the intent in hand. 90% is the figure the issue names.
- **No escape is built.** A line that cannot be covered is excluded by the coverage configuration or marked `pragma: no cover`; the summary lists each added pragma.

### 2. No test is removed

The issue asks to remove the slowest tests of least value. The data does not support it:

- **The ranking by density removes the rules of the repository.** Over all tests, the first 411 tests (1,040 s) lose 43 lines, and they are the invariants and ratchets. This is the trap that the issue names.
- **The tests that may be removed are few.** Over the 2,634 tests that may be removed, the greedy pass gives 106 tests, 154 s and 45 lines (0.05%); 678 tests, 300 s and 437 lines (0.5%); 1,023 tests, 343 s and 864 lines (1%). All 2,634 tests, 416 s, lose 6,892 lines (8.05%), which puts the line coverage at 84.96%, under the new floor.
- **Even all of them do not reach the target.** 416 s of test time is 26 s on 16 workers. The run is 287 s, and the target of the issue is 240 s.
- **The seconds of a test are not its own cost.** The 184 best candidates sum to 192 s in the 16-worker run. Run in one process, one after the other, they take 61 s, and only 16 of them take 1 s or more. The rest of the 192 s is the first import of a heavy library on each worker (the provider factory test takes 5.9 s in the run and 2.7 s in the one-process run) and the load of other processes. A removed test passes its import to the next test on that worker.
- **Several are guards.** The candidates include the tests of the per-test timeout, which hold the harness, and a test that no other RBAC manifest grants roles to the agent.

AGENTS.md rule 2 says to write no compensating code when the premise fails. The change removes no test, and the causes go to the sub-issues. `devops ci mutate` was not run: there is no removal to check, and its own help says that the first run executes the whole suite serially and "can take hours".

### 3. Two documents give the figure, and a test holds them to `pyproject.toml`

Seven documents and the feature request form stated "90%". The change removes the figure from all but `CONTRIBUTING.md` and `docs/TESTING.md`, and a test in `tests/test_agents_md_claims.py` reads `fail_under` and compares the two figures. A change of the floor then changes two sentences, and a stale one fails a test. The alternative, a figure in every document, is what left the knowledge base saying "branch coverage" for a gate that measures lines only.

### 4. The branch figure, for #2163

Measuring branches gives 90.75% (79,649 lines and 19,776 of 23,918 branches). The line figure is 93.01%. At the floor of 85% the margin is 5.75 points with branches and 8.01 points with lines only.

**The cost of branch measurement is not established.** The owner asked for it. The run that differs from the gate only by `--cov-branch` could not be made on a quiet host: on 2026-10-27 the load average was 10 to 39 from other runs, the suite without coverage took 3,540 s of CPU there, and a cost of coverage cannot be told from that noise. Run 2 above took 568 s against 287 s, but it changes the `ctrace` core, the contexts and the branches together. #2373 measures the cost on a quiet host and reports it on #2163.

## Risks / Trade-offs

- **The gate can fail a small change.** A change of 5 source lines with 1 uncovered line is at 80%. The fix is the test that rule 4 of AGENTS.md already asks for first. A line that no test can reach is a design question, and `pragma: no cover` is visible in the summary.
- **The floor is lower.** The owner allowed it. The gate on changed lines keeps the pressure where the change is, and nothing in the pull request lowers a security threshold.
- **The measurement is one host, a few runs.** The time of the same suite on a 16-CPU host was 3 m 28 s idle and 5 m 3 s to 6 m 27 s loaded (the issue), and 4 m 47 s in the run above. A claim that the target of 240 s is met needs the median of many CI runs, not one local run. The sub-issues measure before they change.
- **The protected set is wide.** Citing a file in an OpenSpec document does not mean that all of its tests pin a scenario. A later change may narrow the set with a link from each scenario to its test.
