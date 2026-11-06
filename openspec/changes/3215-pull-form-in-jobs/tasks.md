# Tasks

## 1. The plan body is built by pull_form (behavior)

- [x] 1.1 Add `build_plan_body` to `pull_form`, with tests that a plan body in the form passes `plan_body_problems` and that a placeholder, a short text, a closing keyword and an over-long text raise `ValidationError`.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_pull_form.py`
- [x] 1.2 Build the plan body of the stage job with `build_plan_body` in `pull_request_body`. A refused body goes back to the model once, and a second refusal stops the item. Delete the message `stage_pull_request_body`.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`

## 2. The implement body is built by pull_form (behavior)

- [x] 2.1 Build the body of the implement job with `build_body` in the order text, `Closes`, `Change:`. Stop the item at the step `pull request` when the form refuses the body. Delete the `textwrap.shorten` call of `_why` and the message `implement_pull_body`.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py`

## 3. Documents (documents)

- [x] 3.1 Describe the body in `docs/roadmap/implement.md` and `docs/roadmap/stage.md`.
  Verification: `uv run devops ci --check --only docs`
- [x] 3.2 Check that the change folder is valid.
  Verification: `uv run devops openspec check`

## Workflow follow-up

- The retry of a refused implement body by the model is issue #3599.
- The call of `body_problems` by `devops pr check-readiness` is issue #3259.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
