# Design

## Decisions

- **`least_duration` and not the default `duration_based_chunks`.** The README of pytest-split rates `least_duration` "Better" for the split quality. It deals each test to the group with the least time so far. With no record, each test weighs 1, so the groups take the tests in turn. On the times of one local run of the whole suite (28,260 tests), the largest of five groups is 3.2% above the mean, against 52.5% for `duration_based_chunks`. The shards run under xdist with `--dist worksteal`, so the order of the tests in a group does not matter.
- **No record of test times.** The split reads no `.test_durations`. Every runner collects the same tests in the same order from one commit, and `least_duration` sorts them by name and then by weight (`pytest_split/algorithms.py`), so every runner computes the same groups.
- **The shard writes no JUnit XML report.** Only `devops ci durations` read it. The `-rfEs` summary stays, so the log of a shard still gives the reason of each skip (#4673).
- **The job names stay.** The ruleset requires `Tests & Coverage`, the job that joins the shards. The shard jobs keep the name `Tests & Coverage (shard <n> of <total>)`, which `devops ci job-time` and the implement watch read.
- **The service image shards use the same split.** `service-image-test.yml` passed the file list of `shard_test_files` to pytest. It now passes the split options.

## Rejected alternatives

- **Commit `.test_durations` from `uv run pytest --store-durations --clean-durations`.** The record of the whole suite held 28,260 entries in 3,930,840 bytes. The `check-added-large-files` hook of `.pre-commit-config.yaml` refuses a new file above 500 KB, and an exclusion for the record loosens a check, which only the owner can allow (AGENTS.md rule 5). The record makes the split exact on the times it was measured with, but the split with no record is only 3.2% above the mean on the same times, and the runners differ by more: the whole suite took 355 s to 528 s on different runners (`docs/TESTING.md`).
- **Keep the split by files, with a record of test times.** A record of tests would need a custom sum per module, which is the code that #7500 deletes. Evidence: `shard_test_files` and `recorded_durations` (`src/devops_cli/core/test_selection.py:345-389` at 70dc18c65) and `src/devops_cli/ci/durations.py` (151 lines) were the code behind #4250, #5606 and #5910.
- **A `pytest_ignore_collect` plugin that skips the files of the other shards.** It keeps the saving of #2371 (about 10 s to 15 s of each shard), but it is custom split code again, and pytest-split has no file-level option to feed it (`pytest_split/plugin.py` has no hook before `pytest_collection_modifyitems`).
- **Store the durations in each CI shard and merge them.** `--durations-path` sets both the file that the split reads and the file that `--store-durations` writes (`Base.__init__` in `pytest_split/plugin.py`), so a shard cannot read a committed record and write a separate file. A merge of five files needs a custom step, and a person still commits the result.
