# Tasks

## 1. Durations & Workflow

- [x] 1.1 Refresh `tests/module_durations.json` from the last 20 `main` CI runs via `uv run devops ci durations`
  - Verification: `$ uv run devops ci test tests/ci/test_ci_durations.py`
- [x] 1.2 Expand `test-shard` matrix in `.github/workflows/ci.yml` to `[1, 2, 3, 4, 5, 6]`
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 1.3 Add the 6-shard partition case in `tests/commands/test_ci_shard.py`
  - Verification: `$ uv run devops ci test tests/commands/test_ci_shard.py`

## 2. Documents & Quality Gate

- [x] 2.1 Update `docs/TESTING.md` and `docs/SDLC.md` to document six test shards
  - Verification: `$ uv run devops ci --check --only docs`
- [x] 2.2 Validate OpenSpec and repository static checks
  - Verification: `$ uv run devops openspec check`

Pending a person: after merge, confirm `uv run devops ci job-time --job 'Tests & Coverage'` averages at most 360 s over 20 runs on `main`.
