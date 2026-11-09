# Tasks

## 1. Refuse a placeholder summary in the stage plan

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_title.py`, `tests/support/builders.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_title.py`.

- [x] 1.1 Write `test_the_schema_refuses_a_summary_that_is_a_placeholder_word` and `test_a_plan_that_refuses_a_placeholder_summary_accepts_its_own_summary` in `tests/roadmap/stage/test_roadmap_stage_title.py`, and watch them fail. The first asserts that a summary of `x` raises a `ValueError` that names the placeholder summary, and that `todo` gives the rendered `stage_problem_text_placeholder` text. The second builds the plan's own `StageProposal` with a real summary and asserts that `content_problems` returns no problem, because this group adds the rule that judges the plan itself
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_title.py` fails on the base
- [x] 1.2 Add the `is_placeholder` check to `StageProposal._summary_fits_the_title` in `src/devops_cli/roadmap/stage/stage_change.py`, after the text is shown, and raise `MESSAGES.roadmap.stage_problem_text_placeholder` with the field `summary` and the stripped text
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_title.py` passes

## 2. Refuse a stage plan whose title summary or body is a placeholder

Reads: `src/devops_cli/github/client.py`, `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_draft_readiness.py`. Changes: `src/devops_cli/github/client.py`, `src/devops_cli/roadmap/implement/implement_pull.py`, `tests/roadmap/test_roadmap_draft_readiness.py`.

- [x] 2.1 Write `test_draft_readiness_refuses_a_stage_plan_whose_title_summary_is_a_placeholder`, `test_draft_readiness_refuses_a_stage_plan_whose_body_is_a_placeholder` and `test_draft_readiness_marks_a_complete_stage_plan_ready` in `tests/roadmap/test_roadmap_draft_readiness.py`, and watch them fail. The first two assert that `draft_readiness` returns `Answer.REFUSE` and that the reason names the placeholder, and the third asserts `Answer.READY` for a real title summary, a real body and passing checks
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_draft_readiness.py` fails on the base
- [x] 2.2 Add `title` and `body` fields with empty defaults to `PullStatus` in `src/devops_cli/github/client.py`, so `get_pull_status` fills them from the pull request answer. Add the `STAGE_PLAN` rule to `_judge_completeness` in `src/devops_cli/roadmap/implement/implement_pull.py`: take the text after the first `: `, remove `MESSAGES.roadmap.stage_title_lead` for the item number, and refuse with `stage_problem_text_placeholder` when the summary or the body is a placeholder
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_draft_readiness.py` passes

## 3. Check the change folder

Reads: `openspec/changes/3395-refuse-a-placeholder-plan-summary/`. Changes: None.

- [x] 3.1 Run the OpenSpec gate on the change folder and on the archive
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
