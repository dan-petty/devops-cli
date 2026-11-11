# Tasks

## 1. The conflict row (behavior)

- [x] 1.1 Write the failing tests of the row `pr_conflicts`: its place in the status lane, the delivery filter, one comment for each conflict and head commit, the comment again after a clean round, no change for an unknown state, no action for a clean pull request that is behind, the gauge, a failed read, an unreadable ledger, and one conflict judgment with `devops pr check-readiness`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_pr_conflicts.py`
- [x] 1.2 Add `merge_conflict` to `merge_readiness.py` and call it from the readiness verdict and the implement watch. Add the merge state, the base branch and the default branch to `PullStatus`. Add `roadmap/pr_conflicts.py`, the row `pr_conflicts` after `cloudflare_status`, its interval, its ledger file name, its messages and the gauge `devops_cli_roadmap_conflicted_pulls`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_pr_conflicts.py tests/github/test_merge_readiness.py`
- [x] 1.3 Add `pr_conflicts` to the tests that read the rows of the status lane, and check the triage lane and the model lane in the implement lane test. The due table has 12 rows, so the bound of the row seconds series is 36.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py tests/roadmap/stage/test_roadmap_stage_ready.py tests/roadmap/test_roadmap_run_due_table.py tests/roadmap/test_roadmap_status_rows.py tests/roadmap/test_roadmap_run_lanes.py tests/roadmap/test_roadmap_run_job_rows.py tests/telemetry/test_roadmap_row_seconds.py`

## 2. Documents

- [x] 2.1 Describe the row in k8s/README.md and the lane in CONTEXT.md, and regenerate docs/TELEMETRY.md.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- A Job that rebases a conflicted bot pull request locally and pushes it through the push check needs that check first: #4670.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
