# Tasks

## 1. Raise the process limit of the devcontainer

Kind: behavior. Reads: `.devcontainer/devcontainer.json`, `tests/invariants/test_devcontainer_config.py`. Changes: both.

- [x] 1.1 Add a test that reads `runArgs` and fails when `--pids-limit` is absent or under 4096, and keeps `--gpus all`
  - Verification: `uv run devops ci test tests/invariants/test_devcontainer_config.py`
- [x] 1.2 Add `--pids-limit=8192` to `runArgs` of `.devcontainer/devcontainer.json`
  - Verification: `uv run devops ci test tests/invariants/test_devcontainer_config.py`

## 2. State the limit and the rebuild in CONTRIBUTING.md

Kind: documents. Changes: `CONTRIBUTING.md`.

- [x] 2.1 Add a paragraph to section 2 that states the limit of 8192, the cause of the bursts, and that a person must rebuild the container
  - Verification: `git grep -n "pids-limit=8192" CONTRIBUTING.md`

## Workflow follow-up

- Pending a person: rebuild the container (`Dev Containers: Rebuild Container`), so that the limit applies. `cat /sys/fs/cgroup/pids.max` then shows 8192.
- Work the item will not do: `files.watcherExclude` for `.data` needs a measure first, and the move of the agent worktrees out of the workspace needs a decision of a person.
