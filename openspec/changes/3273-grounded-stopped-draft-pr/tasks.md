# Tasks

## 1. The draft pull request closes the delivered issue (behavior)

- [x] 1.1 Add the failing test: a Planned item that stops after group 1 leaves a draft whose body holds `Closes #<issue>` once and no later body.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py -k leaves_a_draft_that_closes`
- [x] 1.2 Change `implement_pull_body_draft` to start with `Closes #{number}`, and update the docstring of `_publish`.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py tests/roadmap/test_roadmap_implement_planned.py`

## 2. Documents (documents)

- [ ] 2.1 Check that the change folder and the specs are valid.
  Verification: `uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
