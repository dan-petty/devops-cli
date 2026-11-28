# Tasks

## 1. The shard row runs a pytest-split group (behavior)

- [x] 1.1 In `tests/commands/test_ci_shard.py`, add tests that fail on the old code: the row of shard 2 of 4 holds `--splits 4 --group 2 --splitting-algorithm least_duration` and no test path; the split options of the rows of shards 1 and 2 of 2, run with pytest-split on six tests, select each test in exactly one shard; the row writes no JUnit XML report; the dry run names the group.
  - Verification: `$ uv run devops ci test tests/commands/test_ci_shard.py`
- [x] 1.2 In `_resolve_pytest_cmd` of `src/devops_cli/commands/ci.py`, end the sharded row with the split options and `CONST_CI_SHARD_SPLITTING_ALGORITHM`, and drop `--junitxml`.
  - Verification: `$ uv run devops ci test tests/commands/test_ci_shard.py`

## 2. Delete the custom split and record (deletion)

- [x] 2.1 Delete `shard_test_files` and `recorded_durations`, `src/devops_cli/ci/durations.py`, `devops ci durations` with its help and messages, `GitHubClient.get_run_artifact_names`, the `seconds` of `TestCaseOutcome`, the constants `CONST_CI_SHARD_JUNIT_PATH` and `CONST_CI_TEST_DURATIONS_PATH`, `tests/ci/test_ci_durations.py` and the split tests of `tests/commands/test_ci_shard.py`.
  - Verification: `$ ! git grep -n -F shard_test_files -- src tests .github`
  - Verification: `$ ! git grep -n -w -F recorded_durations -- src tests .github`
  - Verification: `$ ! git grep -n -F devops_cli.ci.durations -- src tests .github`
  - Verification: `$ ! git grep -n -F get_run_artifact_names -- src tests .github`
  - Verification: `$ ! git grep -n -F module_durations -- src tests .github`
  - Verification: `$ ! git grep -n -F CONST_CI_SHARD_JUNIT_PATH -- src tests .github`

## 3. The dependency and the record (data)

- [x] 3.1 Add `pytest-split==0.11.0` to the `dev` group of `pyproject.toml` and run `uv lock`. Delete `tests/module_durations.json` and its line in `.gitattributes`.
  - Verification: `$ uv lock --check`

## 4. The workflows (workflow)

- [x] 4.1 In `.github/workflows/ci.yml`, upload only `.data/.coverage` from a shard and fix the comment of the job `test-shard`. In `.github/workflows/service-image-test.yml`, pass `--splits`, `--group` and `--splitting-algorithm least_duration` to pytest in place of the file list.
  - Verification: `$ uv run devops ci --check --no-cache --only actionlint,zizmor`

## 5. The documents (documents)

- [x] 5.1 Regenerate the CLI reference, and fix `docs/TESTING.md`, `docs/SDLC.md` and the plan of change 2176, which named the removed command and record.
  - Verification: `$ uv run devops docs generate`
  - Verification: `$ uv run devops ci docs`
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Step 2 of #7500, the test selection with pytest-testmon, is #7511.
- Step 3 of #7500, the job-time alarm with `timeout-minutes` and an alert rule, is #7513.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
