# Proposal

## Why

Issue #2356: the test step is at its budget of 300 s, and AGENTS.md rule 5 makes a check that averages more than 5 minutes a P0 bug. The owner decided on 2026-10-27 that the coverage floor goes down to 85% and that the changed lines of a pull request are gated. Alone, a lower floor lets untested code in. With the gate on the changed lines, the pressure stays on the code that a pull request changes.

The issue also asks to measure first and to remove the slowest tests of least value. The measurement (design.md) shows that removal does not pay. 83% of the test time is in tests that no one may remove: invariants, ratchets, contract suites, security tests and tests that an OpenSpec change cites. The other 17% looks slow only because of work that each of the 16 workers repeats. This change records that result, makes no removal, and sends the real causes to sub-issues.

## What Changes

- `fail_under` in `pyproject.toml` goes from 90 to 85.
- The `Changed-Line Coverage` step of `ci.yml` runs `diff-cover` with `--fail-under 90`, so the `Tests & Coverage` job fails when under 90% of the changed lines of a pull request are covered. The step still writes the list of added `pragma: no cover` lines to the job summary when it fails, and then exits with the status of `diff-cover`. A pull request that changes no line of `src/` has no figure and passes.
- The statements of the floor in `CONTRIBUTING.md`, `docs/TESTING.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, the feature request form and three knowledge base documents change. Two documents (`CONTRIBUTING.md` and `docs/TESTING.md`) give the figure; the others name the gate without a figure. A test in `tests/test_agents_md_claims.py` holds those two figures to `fail_under`. The knowledge base documents no longer say "line and branch": the gate measures lines only.
- No test is removed. design.md gives the measurement and the evidence.
- The speed-ups of step 4 of the issue are filed as sub-issues, each with its own change and its own pull request. tasks.md names them.
- The change sets `skip_specs: true` in `.openspec.yaml`: no command, option or message changes.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Configuration and CI: `pyproject.toml`, `.github/workflows/ci.yml`.
- Tests: `tests/test_ci.py` (the workflow test now expects the gate), `tests/test_agents_md_claims.py` (the guard on the stated floor).
- Documents: `CONTRIBUTING.md`, `docs/TESTING.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `.github/ISSUE_TEMPLATE/feature_request.yml`, and three knowledge base documents under `src/devops_cli/ai/knowledge_base/`.

## Feasibility

- `diff-cover` 10.6.0 (`--help`) has `--fail-under SCORE`: "Returns an error code if coverage or quality score is below this value". A run of the real `run` block of the step in a scratch repository gave exit 0 with "No lines with coverage information in this diff" for a change with no source line, exit 0 for 10 of 10 changed lines covered, and exit 1 with "src/devops_cli/m.py (50.0%): Missing lines 16-20" for 5 of 10. The summary held the pragma section in the third case.
- The suite measured on 2026-10-27 at the base commit: 11,285 tests passed, and the line coverage is 93.01% (79,649 of 85,639 statements). The new floor leaves 8.01 points.
- The premise "remove the slow tests of least value" does not hold. design.md gives the numbers. AGENTS.md rule 2 says to write no compensating code, so the change removes no test and files the causes.

## Existing Tool Considered

- `diff-cover` (already a dev dependency, and already in `ci.yml`) is the gate on the changed lines. The change builds nothing for it.
- `coverage.py` dynamic contexts (`--cov-context=test`) and `pytest --durations=0` gave the per-test lines and seconds. A script of about 150 lines of the standard library and the public API of `coverage` joined them. The script is a scratch file and is not committed: it answers one question once, and design.md gives the commands to repeat it. Cost: about 15,000 tokens to write and fix the script, and about one hour of elapsed time, most of it waiting for full runs.
- `pytest-split`, `pytest-testmon` and `mutmut` stay candidates for the sub-issues. `devops ci mutate` was not run: its own help says the first run executes the whole suite serially and "can take hours", and there is no removal to check.
