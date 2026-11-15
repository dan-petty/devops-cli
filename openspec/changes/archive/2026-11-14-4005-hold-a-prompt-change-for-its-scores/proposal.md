# Proposal

## Why

A change of the stage prompt moves the quality of the plans, and only a live eval score shows that it moves it up. The step shell holds no model key, so the implement job cannot run the live eval and cannot write the score. The fast checks pass, the step ticks its task, and a person meets the missing evidence at review (#4005, split from #3830).

## What Changes

- `read_draft` reads the compare files once for every kind, and `Draft` holds them in `files`.
- `draft_readiness` refuses a draft that changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` and whose body lacks the last `Base eval score:` line or the last `Head eval score:` line, or whose last line of a marker holds no number. The reason names each missing marker.
- The ready step of the implement job passes its local diff to the draft, so the rule holds the item before `mark_ready`, and its stop comment names the missing score.
- The body form accepts the two score lines after the `Change:` line.
- Offline tests cover no score, one score, both scores, a repeated marker and a marker with no number.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/pull-request`: a prompt change waits for its live eval scores.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_draft_readiness.py`, `tests/roadmap/test_roadmap_pull_form.py`
- Documents: `docs/ROADMAP_WORKFLOW.md` and `docs/TESTING.md` already hold the score rule of #3830; this change adds the draft gate that reads it.

## Feasibility

- Read on `origin/main`, 2026-11-14. `src/devops_cli/roadmap/implement/implement_pull.py:210:def draft_readiness(` judges every draft, and `:251:def read_draft(` reads the compare files for an implement pull request only.
- `src/devops_cli/roadmap/stage/stage_change.py:267:STAGE_EVAL_PROMPT_PATH` holds the prompt path.
- The ready step reads the draft at `src/devops_cli/roadmap/implement/implement_run.py:1774:def _ready(` and stops the item with the reason.
- `src/devops_cli/roadmap/pull_form.py` accepts trailer lines after `Change:`, and `tests/roadmap/test_roadmap_pull_form.py:184:def test_the_attribution_lines_after_the_change_line_are_allowed()` shows the form.
- `uv run pytest tests/roadmap/test_roadmap_draft_readiness.py tests/roadmap/test_roadmap_pull_form.py tests/roadmap/implement` passes after the change.

## Existing Tool Considered

No open, maintained tool holds a draft until a body holds two eval scores. GitHub's required status checks gate a merge and cannot hold a draft, and no check can run a live eval without the model key. The project builds the rule in its one readiness function: about 4,000 tokens to build and 200 a quarter to keep.

## Dependencies

#3398 is closed and #3830 is ready.
