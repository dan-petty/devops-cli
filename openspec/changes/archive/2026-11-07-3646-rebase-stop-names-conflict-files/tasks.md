# Tasks

## 1. A conflict stop names its files

Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/store.py`, `tests/roadmap/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_stop_clear.py`.

- [x] 1.1 Write the failing tests first: the comment and the record name each conflicted file for a conflict at the start and before the push, a retry and a clear rule of the Service clear the record, a list above the limit is cut with a count, and a secret in a path is masked
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py`
- [x] 1.2 Read the unmerged files in `_sync` before the abort, add `conflict_files` to `_StopError`, add the record key `implement.conflict`, write it in `stop`, and clear it on a retry and in `stop_clear.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py`

## 2. Documents

Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 2.1 Add the record key `implement.conflict` to the table of job record keys
  - Verification: `git grep -n "implement.conflict" -- docs/ROADMAP_WORKFLOW.md`
