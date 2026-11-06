# Tasks

## 1. The tests of the shard split (behavior)

- [x] 1.1 In `tests/commands/test_ci_shard.py`, add tests that fail on the old code: the shards 1 to N cover every test module of `tests/` once for N of 2, 3 and 4 with no empty list; two calls give the same lists in any order of asking; the split deals the heaviest file first to the lightest shard; the planned command of shard 2 of 4 holds its paths and none of `--splits`, `--group` and `--splitting-algorithm`; the unsharded row holds no path.
  Verification: `uv run devops ci test tests/commands/test_ci_shard.py`

## 2. The test row passes the files of its shard (behavior)

- [x] 2.1 Add `_shard_test_files` to `src/devops_cli/commands/ci.py`, and end the command of a sharded `test` row with its result. Drop `--splits`, `--group` and `--splitting-algorithm`, and fix the docstring of `_resolve_pytest_cmd`.
  Verification: `uv run devops ci test tests/commands/test_ci_shard.py tests/commands/test_test_selection.py`

## 3. Remove `pytest-split`, and fix the documents (dependency, documents, workflow)

- [x] 3.1 Remove `pytest-split` from `pyproject.toml`, run `uv lock`, and fix the text in `.github/workflows/ci.yml`, `docs/SDLC.md` and `docs/TESTING.md`, which gets the paragraph on collection.
  Verification: `! git grep -il pytest-split -- . ':!openspec/changes/archive' ':!openspec/changes/2371-measure-and-cut-what-each-of' ':!openspec/changes/archive'`
- [x] 3.2 Check the spec delta and the other changes.
  Verification: `uv run devops openspec check`

## Workflow follow-up

- Pending a person: the pull request comment records the measurements of the issue: the test counts of the four lists against the whole suite (criterion 4), the CPU time of `pytest --collect-only -q -n 0 -p no:cacheprovider` for one list against the whole suite (criterion 5, at most 75%), the summed CPU of the four shard commands (criterion 6), and the durations of the four `Tests & Coverage Quality Gate` steps of one run (criterion 6a, the slowest at most 15% above the mean).
- Pending a person: after the merge, compare `uv run devops ci job-time` with the mean recorded just before the merge (criterion 7), and record both on #2371.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
