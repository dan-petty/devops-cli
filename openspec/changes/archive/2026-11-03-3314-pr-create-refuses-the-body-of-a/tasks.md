# Tasks

## 1. Judge a plan body by the form of a plan

Reads: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/roadmap/grounding.py`. Changes: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_pr_form_check.py`.

- [x] 1.1 In `tests/commands/test_pr_form_check.py`, assert that a plan title with a `Plans #<issue>` body opens a draft, that a plan body with a `Closes` line, a wrong issue or a wrong `Change:` issue opens nothing, and that a delivery title still needs `Closes`. Verify that `uv run devops ci test tests/commands/test_pr_form_check.py` fails on the base
- [x] 1.2 Add `plan_body_problems` to `src/devops_cli/roadmap/pull_form.py`, use it in `_form_checked` when `plan_issue` reads the title, and add the four messages to `src/devops_cli/lang/en/messages.py`. Verify that `uv run devops ci test tests/commands/test_pr_form_check.py` passes

## 2. Document the plan form

Reads: `CONTRIBUTING.md`. Changes: `CONTRIBUTING.md`.

- [x] 2.1 In `CONTRIBUTING.md`, say that a plan pull request has the line `Plans #<issue>` in place of `Closes`, and verify that `uv run devops ci docs` passes

## Criteria

- A plan body in the form of a plan opens a draft with `devops pr create`.: group 1
- A delivery body still needs a `Closes` line.: group 1

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
