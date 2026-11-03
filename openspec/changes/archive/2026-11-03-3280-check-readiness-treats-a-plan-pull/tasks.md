# Tasks

## 1. Add the plan rules to the grounding module

Reads: `src/devops_cli/roadmap/grounding.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/grounding.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_grounding.py`.

- [x] 1.1 In `tests/roadmap/test_grounding.py`, assert that `plan_issue` reads 3183 from `docs(openspec): plan #3183 add plan-check` and None from a delivery title, and that `plan_blockers` returns no blocker for a valid plan and one blocker for each of: no Plans line, a closing keyword, no active folder file, a living spec path. Verify that `uv run devops ci test tests/roadmap/test_grounding.py` fails on the base
- [x] 1.2 Add `plan_issue` and `plan_blockers` to `src/devops_cli/roadmap/grounding.py`, using `closing_keyword_in`, and one message for each rule to `src/devops_cli/lang/en/messages.py`. Verify that `uv run devops ci test tests/roadmap/test_grounding.py` passes

## 2. Judge a plan by its rules in readiness

Reads: `src/devops_cli/github/merge_readiness.py`, `tests/github/test_merge_readiness.py`. Changes: `src/devops_cli/github/merge_readiness.py`, `tests/github/test_merge_readiness.py`.

- [x] 2.1 In `tests/github/test_merge_readiness.py`, assert that a valid plan payload is ready with no closing-issues request, and that a plan with `Closes #3183` has one blocker. Verify that `uv run devops ci test tests/github/test_merge_readiness.py` fails on the base
- [x] 2.2 In `_judge_grounding`, apply `plan_blockers` and read no closing issues when `plan_issue` of the title names an issue. Verify that `uv run devops ci test tests/github/test_merge_readiness.py` passes

## 3. Document the plan rules

Reads: `docs/SDLC.md`. Changes: `docs/SDLC.md`.

- [x] 3.1 In `docs/SDLC.md`, add after the archive sentence of Phase 6 that a plan pull request (title `docs(openspec): plan #<issue>`) needs `Plans #<issue>` and the active change folder, and that readiness asks it for no closing issue and no archive, and verify that `uv run devops ci docs` passes

## Criteria

- A valid plan pull request passes readiness with no closing-issue or archive blocker.: group 2
- Each rule of a plan gives one blocker.: group 1

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
