# Proposal: #7500

## Why

Issue #7500 asks to replace the custom code that splits and times the tests of CI with open tools. This change is step 1 of the issue: the test shards and their record of durations.

The custom split (`shard_test_files` in `src/devops_cli/core/test_selection.py`) dealt test modules to the shards by a record of module seconds, `tests/module_durations.json`. The command `devops ci durations` (`src/devops_cli/ci/durations.py`) wrote that record from the JUnit XML reports of the shards of CI. Six issues of the shards and the selection (#2868, #4250, #4472, #5606, #5612, #5910) and three runs over the time budget (#6130, #6262, #6522) came from this code or from its unbalanced shards. On main, the last 5 runs had a spread of up to 112 s between the fastest and the slowest shard of one run.

pytest-split does the same work: `--splits <total> --group <n>` runs one group, and `least_duration` deals the tests to the groups.

## What Changes

- `devops ci --shard <n> --shards <total>` passes `--splits <total> --group <n> --splitting-algorithm least_duration` to pytest, and no list of test files. The test row of a shard writes no JUnit XML report.
- `pytest-split` 0.11.0 joins the `dev` group of `pyproject.toml` and `uv.lock`.
- `tests/module_durations.json` is deleted, and no record replaces it: each test weighs the same (see `design.md`).
- Deleted: `shard_test_files` and `recorded_durations` (`core/test_selection.py`), `src/devops_cli/ci/durations.py`, the command `devops ci durations` with its help and messages, `GitHubClient.get_run_artifact_names`, the `seconds` of `TestCaseOutcome`, the constants `CONST_CI_SHARD_JUNIT_PATH` and `CONST_CI_TEST_DURATIONS_PATH`, and their tests.
- `.github/workflows/ci.yml` uploads only the coverage data of a shard. `.github/workflows/service-image-test.yml` passes the split options to pytest in the service image.
- A devops command and its options change, so the specs `ci-test-shards` and `ci-job-time` change through deltas.
- `docs/TESTING.md`, `docs/SDLC.md`, the CLI reference and the plan of change 2176 stop naming the removed command and record.
- Steps 2 and 3 of the issue (test selection with pytest-testmon, and the job-time alarm) are out of scope. See "Workflow follow-up" in `tasks.md`.

The change fits one pull request.

## Capabilities

- `ci-test-shards`: MODIFIED, ADDED and REMOVED requirements.
- `ci-job-time`: MODIFIED requirement "Only the wanted runs are read", which no longer names `devops ci durations`.

## Impact

- Code: `src/devops_cli/commands/ci.py`, `src/devops_cli/core/test_selection.py`, `src/devops_cli/github/client.py`, `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`. Deleted: `src/devops_cli/ci/durations.py`.
- Tests: `tests/commands/test_ci_shard.py`. Deleted: `tests/ci/test_ci_durations.py`.
- Data: `tests/module_durations.json` and its line in `.gitattributes` are deleted.
- Dependencies: `pyproject.toml`, `uv.lock`.
- Workflows: `.github/workflows/ci.yml`, `.github/workflows/service-image-test.yml`. The job names stay, so the required check `Tests & Coverage` of the ruleset does not change.
- Documents: `docs/TESTING.md`, `docs/SDLC.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ci.md`, `openspec/changes/2176-use-mutation-to-merge-or-delete/`.

## Feasibility

Checked on 2026-11-28 at `origin/main` 70dc18c65.

- pytest-split 0.11.0 (2026-02-03, MIT, not archived) reads its options in `src/pytest_split/plugin.py`: `--store-durations`, `--durations-path` (default `.test_durations` in the working directory), `--splits`, `--group`, `--splitting-algorithm` and `--clean-durations`. It requires `pytest>=5,<10`; this repository pins pytest 9.2.0. `uv lock` resolved it with no other change.
- `least_duration` (`src/pytest_split/algorithms.py`) sorts the tests by `str(item)` and then by duration, with stable sorts, so a tie keeps the collection order. Every runner and every xdist worker collects the same tests in the same order (`-p no:randomly` in `addopts`), so all compute the same groups.
- The plugin selects in `pytest_collection_modifyitems` (`trylast=True`), after collection. So each xdist worker collects the whole suite again. #2371 measured the cost: a quarter of the files collects in 66% of the CPU time of the whole suite, about 10 s to 15 s of wall time in each shard. The pull request compares the shard times with the last 5 runs of `main`.
- `--store-durations` under xdist records every test: a run of `tests/ci` (265 tests, `-n logical`) wrote 265 entries. One local run of the whole suite wrote 28,260 entries in 3,930,840 bytes.
- A replay of the algorithms of pytest-split 0.11.0 on those times, for five shards: `least_duration` with no record puts the largest shard 3.2% above the mean, with the record 0%, and `duration_based_chunks` with no record 52.5%. The old split by modules and `tests/module_durations.json` puts it 40.1% above the mean.
- The required checks of the live ruleset are `Static Analysis`, `Tests & Coverage` and `Semantic PR title` (`devops gh api repos/dan-petty/devops-cli/rulesets/<id>`). The shard jobs keep their names.

## Existing Tool Considered

- **pytest-split 0.11.0** (github.com/jerry-git/pytest-split, MIT) covers the split, and its `--store-durations` covers a record. This change uses the split.
- **pytest-xdist `--dist loadfile`/`loadgroup`** spread tests over the workers of one runner, not over runners.
- **pytest-test-groups** splits by test count and reads no times.
- Internal code deleted: `shard_test_files`, `recorded_durations`, `src/devops_cli/ci/durations.py` (151 lines), `devops ci durations` and its plan, `get_run_artifact_names`, the JUnit `seconds` of `TestCaseOutcome`, the two constants, the help and message strings, and 29 tests (20 of the split, 9 of the record).
