# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: a refused reply logs its answered searches on the result line and keeps them in its failure, only an answered search counts, a `url` refusal logs each refused URL at WARNING, a `no_facts` refusal logs no URL, and a stopped run logs its searches
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_job_result.py`
- [x] 1.2 Add `searches` to `CheckFailure`, set it on each failure of an agent run, write it on the result line, and log each refused URL in `validate_reply`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_job_result.py`

## 2. Documents

- [x] 2.1 Say in `docs/roadmap/alternatives.md` and `docs/roadmap/job-success.md` that the result line of a failed check gives its answered searches and that a `url` refusal logs each refused URL
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #6394 fixes the cause of the `url` refusals when the new log lines show it.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
