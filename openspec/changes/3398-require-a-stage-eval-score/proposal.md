# Proposal

## Why

`docs/ROADMAP_WORKFLOW.md` requires a pull request that changes the stage prompt or a stage check to state the score of the same model before and after the change. No check enforces it, so a pull request can become ready with no replay command and no score (#3398).

## What Changes

- `assess_merge_readiness` holds a pull request that changes a stage trigger path to its stage eval evidence, with the blocker kind `stage_eval`.
- The trigger paths are the stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` and the stage check modules `stage_change.py`, `stage_form.py`, `stage_paths.py`, `stage_criteria.py`, `stage_eval_gates.py` and `stage_move.py`.
- The evidence is a replay (`uv run devops roadmap eval stage --replay` with a number before and after) or a live run (one `--model` name and a score before and after). A body with no command, no number, two models, or a `--model` flag with no name is refused.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-merge-readiness`: A pull request that changes the stage prompt or a stage check states its stage eval evidence.

## Impact

- Code: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/github/test_merge_readiness.py`

## Feasibility

- `assess_merge_readiness` already reads the changed files of the pull request and the body.
- `stage_eval_problems` is a pure function, so the four refused forms and the passing forms run offline.
- Verification commands: `uv run devops ci test tests/github/test_merge_readiness.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

No open, maintained tool covers a project-specific readiness rule. The change extends the readiness checks of this repository and adopts no new dependency.
