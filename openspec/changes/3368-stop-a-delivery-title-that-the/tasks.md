# Tasks

## 1. Guard the delivery title in both write paths

Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_implement_pull.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `tests/roadmap/test_roadmap_implement_title.py` (new).

- [ ] 1.1 Write `tests/roadmap/test_roadmap_implement_title.py` with two offline cases, an issue title `Add a flag` and an issue title `wip(cli): add a flag`, and assert for each a stop whose message holds the title problem and the issue title, no `create_draft_pull` call, no `update_pull` call and, after a first push, one branch deletion
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_title.py` fails on the base
- [ ] 1.2 In `src/devops_cli/roadmap/implement_run.py`, add one helper that runs `title_problems(title, declared)` from `src/devops_cli/roadmap/pull_form.py` and raises the job's stop error with each problem and the issue title. Call it in `_publish` on the delivery title before `create_draft_pull`, and in `_pull_request` before `update_pull`. When `_publish` has already pushed the branch, run the existing draft-refusal cleanup that deletes the branch on `origin` before the stop
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_title.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
