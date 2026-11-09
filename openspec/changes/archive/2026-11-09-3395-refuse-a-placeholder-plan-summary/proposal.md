# Proposal

## Why

The stage job refuses a placeholder in the plan text, but not in the summary of the pull request title (#3395). A plan pull request can open with the title `docs(openspec): plan #3321 x` and the body `x`, and every check passes. The title summary and the body then name no work, and the item spends a full check round on them. #3200 and #3367 cover other fields.

## What Changes

- Add a guard to `StageProposal._summary_fits_the_title` in `src/devops_cli/roadmap/stage/stage_change.py`: it refuses a summary whose whole text is a placeholder word through `is_placeholder` of `src/devops_cli/roadmap/pull_form.py`, with the existing `stage_problem_text_placeholder` message for the field `summary`.
- Add the `title` and the `body` of a pull request to `PullStatus` in `src/devops_cli/github/client.py`, with empty defaults, so the draft readiness sees them with no new request.
- Add a `STAGE_PLAN` rule to `_judge_completeness` in `src/devops_cli/roadmap/implement/implement_pull.py`: it refuses a stage plan whose title summary or body is a placeholder, with the reason that names the placeholder.
- Add `test_the_schema_refuses_a_summary_that_is_a_placeholder_word` and `test_a_plan_that_refuses_a_placeholder_summary_accepts_its_own_summary` to `tests/roadmap/stage/test_roadmap_stage_title.py`.
- Add tests to `tests/roadmap/test_roadmap_draft_readiness.py` for a placeholder title summary, a placeholder body and a complete stage plan.
- Add the summary problem to `PlanUnderTest.of_case` in `src/devops_cli/roadmap/stage/stage_eval_gates.py`, and record the `kind` gate defect of the placeholder summary in the golden case `3167-a-comment-by-a-person-on`, so the replay matches the schema.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The stage plan refuses a placeholder summary.
- `roadmap-implement-job`: The draft readiness refuses a stage plan whose title summary or body is a placeholder.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/github/client.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_title.py`, `tests/roadmap/test_roadmap_draft_readiness.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`, `tests/fixtures/roadmap_eval/stage/3167-a-comment-by-a-person-on/case.json`

## Feasibility

- A probe at the staging commit `54e5d464` returned `title_problems("docs(openspec): plan #3321 x") == []` and `is_placeholder("x") is True`, so the title lead hides the placeholder summary from the form check.
- The same probe built a `StageProposal` with the summary `x` and `content_problems` returned `[]`, so the schema and the content gate accept the placeholder today.
- `_summary_fits_the_title` at `src/devops_cli/roadmap/stage/stage_change.py:614` checks the blank text, the cut text and the length, and calls no placeholder rule.
- `_plan_texts` at `src/devops_cli/roadmap/stage/stage_change.py:1039` omits `summary`, so `content_problems` judges no summary.
- `PullStatus` at `src/devops_cli/github/client.py:76` holds `state`, `draft`, `merged`, `head_sha`, `head_ref`, `labels` and `closed_at`, and no title and no body.
- `_judge_completeness` at `src/devops_cli/roadmap/implement/implement_pull.py:124` returns `None` for `DraftKind.STAGE_PLAN`, so a plan is complete when it opens.
- `get_pull_status` at `src/devops_cli/github/client.py:391` reads `GET /repos/{repo}/pulls/{number}`, and that answer already holds the title and the body, so the new fields need no second request.
- First checks against the real system: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_title.py` and `uv run devops ci test tests/roadmap/test_roadmap_draft_readiness.py`.

## Existing Tool Considered

No open, maintained external tool covers a project-internal roadmap rule. The change reuses `is_placeholder` and the existing `stage_problem_text_placeholder` message of `src/devops_cli/roadmap/pull_form.py` and `src/devops_cli/lang/en/messages.py`; it builds no new rule and no new message. The written cost is about 10000 tokens to build, keep and fix it, and 30 minutes of elapsed time. The change deletes no code.

## Dependencies

None.
