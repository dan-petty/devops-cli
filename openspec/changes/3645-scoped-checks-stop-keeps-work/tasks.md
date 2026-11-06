# Tasks

## 1. A stop in the scoped checks keeps the finished work (behavior)

- [x] 1.1 Change the four tests of the stops in the scoped checks (a check that no fix repairs, a fix step that stops, a command that runs out of time in a fix step, an error) to assert that `origin` holds the commits of both groups and that the comment names the branch and its last commit. Add the tests of the next Job and of the draft with no ready request. They fail before the code changes.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job_scoped.py`
- [x] 1.2 Let the judge take a branch whose change is archived (`_plan_reason` in `implement.py`), so that the next Job takes the kept work.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job_scoped.py tests/roadmap/test_roadmap_implement_plan_reason.py tests/roadmap/test_roadmap_implement_selection.py`
- [x] 1.3 Add the flag `kept_branch` to `_StopError`, set it for each stop in `_scoped_checks`, stop forcing `push` to false there, and let `_kept_note` name the branch and its last commit when the flag is set and no `wip:` commit exists. Add the message `implement_stop_kept_branch`.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job_scoped.py tests/roadmap/test_roadmap_implement_wip_job.py tests/roadmap/test_roadmap_implement_job.py`

## 2. Documents (documents)

- [ ] 2.1 State the new push rule in `docs/ROADMAP_WORKFLOW.md`, and in the module docstring of `implement_run.py`.
  Verification: `uv run devops ci --check --only docs`
- [ ] 2.2 Check that the change folder is valid.
  Verification: `uv run devops openspec check`

## Workflow follow-up

- #3273 (a stopped step opens a draft pull request) works in `_push_passed` and `_publish`, and this change leaves both as they are.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
