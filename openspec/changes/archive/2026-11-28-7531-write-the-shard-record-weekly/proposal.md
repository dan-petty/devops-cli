# Proposal

## Why

The required check `Tests & Coverage` averages about 362 s against the limit of 360 s (AGENTS.md rule 5). Its time is the slowest test shard plus the join job. The split of the shards weighs each test module by its seconds in `tests/module_durations.json` (#5247), and nothing wrote that record again after 2026-11-17 (#6248). It held no seconds for 143 of the 1,437 test modules, such as `tests/ai/test_project_digest.py` (59.8 s in CI). The split weighed these modules by lines, and the shards went out of balance (#7531).

## What Changes

- `uv run devops ci durations` writes the record again from the last 20 push runs of `main`.
- A new workflow `test-durations.yml` runs the same command each Monday and on a manual run. `peter-evans/create-pull-request` opens one pull request with the new record, or updates the open one. It uses a token of the release App, so the checks of the pull request run. A person merges it.
- `docs/TESTING.md` and `docs/SDLC.md` name the weekly refresh.
- The change alters a CI workflow and data, and no behavior that a consumer observes, so it has no spec delta (`skip_specs: true`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Workflows: new `.github/workflows/test-durations.yml`.
- Data: `tests/module_durations.json`.
- Documents: `docs/TESTING.md` (Run time), `docs/SDLC.md`.
- The change fits one pull request.

## Feasibility

- `uv run devops ci durations` (devops-cli 0.232.3) exited 0 on 2026-11-28 and wrote the mean seconds of 1,436 test modules from 20 runs. The read took 3 min 14 s.
- The old record held 1,302 modules: 143 modules of the tree had no seconds, and 8 recorded modules no longer exist.
- The new means measure the two splits (`shard_test_files` of `core/test_selection.py` with each record). The split of the old record gives the shards 730 / 713 / 687 / 696 / 599 s (spread 131 s). The split of the new record gives 685 s to each shard.
- The last 5 push runs of `main` are 46103047841, 46102488879, 46102127064, 46098309980 and 46098277385. In each run, the slowest shard had 266 s to 414 s more JUnit seconds than the fastest shard. Shard 4 of two runs with the same files took 858 s and 498 s. So the speed of the runner gives a part of the spread, and no record removes that part.
- The `release` environment admits the branch `main` (deployment branch policy), and a scheduled run runs on `main`. `release.yml` and `release-merge.yml` already mint the release App token with `contents: write` and `pull-requests: write`.
- The `action.yml` of `peter-evans/create-pull-request` v8.1.3 (2026-11-10, MIT) has the inputs `sign-commits`, `add-paths`, `branch`, `delete-branch` and `labels`.

## Existing Tool Considered

- `devops ci durations` is the existing command that writes the record. The change adds no code to it.
- `peter-evans/create-pull-request` opens and updates the pull request. It commits only when the file changed, keeps one branch and one pull request, and makes a verified commit as the App. The change builds no script with `git push` and `gh pr create`.
- In #7500, pytest-split was slower than the custom split (437 s against 362 s). The owner kept the custom split.
- The change deletes no internal code.
