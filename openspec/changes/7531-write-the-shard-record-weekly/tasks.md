# Tasks

## 1. Write the record again

Kind: other.

Changes: `tests/module_durations.json`.

- [x] 1.1 Run `uv run devops ci durations` and commit the record of 1,436 modules from 20 runs.
  - Verification: `$ uv run devops ci test tests/commands/test_ci_shard.py`

## 2. Refresh the record each week

Kind: other.

Changes: `.github/workflows/test-durations.yml`.

- [x] 2.1 Add the workflow `test-durations.yml`. The job `record` runs `devops ci durations` and uploads the record. The job `pull-request` opens or updates the pull request with the release App token.
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`

## 3. Documents

Kind: other.

Changes: `docs/TESTING.md`, `docs/SDLC.md`.

- [x] 3.1 Name the weekly refresh in `docs/TESTING.md` (Run time) and `docs/SDLC.md`.
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- Pending a person: merge each weekly pull request of `test-durations.yml`. The first scheduled run starts after the merge of this change; a manual run (`workflow_dispatch`) on `main` proves it earlier.
