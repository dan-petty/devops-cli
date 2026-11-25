# Tasks

## 1. Behavior

- [x] 1.1 Add failing test in `tests/roadmap/test_roadmap_watch_row.py` proving zero `/check-runs` requests for a backed-off failed head in REST fallback
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_watch_row.py`
- [x] 1.2 Extract `_failed_head_in_backoff` in `src/devops_cli/roadmap/watch_row.py` and guard `read_check_runs` in `_process_rest_pulls`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_watch_row.py`

## 2. Documents

- [x] 2.1 Validate OpenSpec artifacts against `roadmap-watch-row` spec
  - Verification: `$ uv run devops openspec check`
