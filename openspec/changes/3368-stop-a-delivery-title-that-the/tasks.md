# Tasks

## 1. Add the two missing refusal tests

Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/pull_form.py`, `tests/roadmap/test_roadmap_implement_job.py`. Changes: `tests/roadmap/test_roadmap_implement_job.py`.

- [ ] 1.1 Add a test for an issue title `wip(cli): add a flag`, whose type the project does not declare, and assert the job stops the item and writes no pull request title
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py`
- [ ] 1.2 Add a test for a Planned item whose delivery title has no type, and assert the job stops before `_publish` pushes, so `origin` holds no branch and no draft pull request exists
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
