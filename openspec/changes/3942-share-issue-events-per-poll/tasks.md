# Tasks

## 1. Share the issue events of one poll

Reads: `src/devops_cli/roadmap/run.py`. Changes: the same file and `tests/roadmap/test_roadmap_run_github_requests.py`.

- [ ] 1.1 Add `PollCache` and let `_fetch_filtered_changes` read through it.
- [ ] 1.2 Pass one `PollCache` from `service_jobs` through `service_job` to `run_due_jobs`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_lanes.py` passes
- [ ] 1.3 Add the tests: three lanes send one request, the next poll sends a new one, a later cutoff filters, and two repositories keep apart.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_github_requests.py` passes
