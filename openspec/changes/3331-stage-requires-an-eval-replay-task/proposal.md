# Proposal

## Why

`docs/ROADMAP_WORKFLOW.md:233` requires a pull request that changes the stage prompt or a stage check to state the model score before and after the change. No check enforces it, so plans such as the one of #3252 miss the eval replay task and their implementation pull requests fail merge readiness or need rework. #3331 makes the stage job refuse such a plan.

## What Changes

- Add a replay rule to `check_proposal`: a plan whose groups change the stage prompt, `stage_change.py` or `stage_eval_gates.py` is refused unless one group task holds `uv run devops roadmap eval stage --replay` with the words `score`, `before` and `after`.
- Refuse a plan that changes a trigger path and holds the replay command with no before and after score, with a problem that asks for the score.
- Add tests to `tests/roadmap/test_roadmap_stage_form.py` for the refusal, the missing score, the passing plan and a plan that changes no trigger path.
- Name the trigger paths and the required task text in `docs/ROADMAP_WORKFLOW.md` so the rule and the check agree.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A plan that changes the stage prompt or a stage gate gives the eval replay task

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_stage_form.py`

## Feasibility

- The premise holds. `probes` says: "The path `src/devops_cli/roadmap/stage_eval_gates.py` is a file of the staging commit." and "The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit."
- The rule that the issue cites is in the context: "A pull request that changes the stage prompt (`roadmap_stage_change.md`) or a check of the stage job (`check_proposal` and the gates it calls) states the score of the same model before and after the change."
- The context lists `check_proposal` in `src/devops_cli/roadmap/stage_change.py` with its callers `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/roadmap/stage_specs.py` and `src/devops_cli/roadmap/stage_verify.py`.
- The context shows no check of the eval replay task in `src/devops_cli/roadmap/stage_change.py`, so the rule is new.
- The golden cases of the replay change no trigger path, so the new rule refuses none of them: the first check is `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py`.
- The form rules run first: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py`.
- The whole stage job runs next: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`.

## Existing Tool Considered

No open, maintained tool or library covers a project-specific rule of a stage plan. The project builds the check in `src/devops_cli/roadmap/stage_change.py`. Cost: about 12,000 tokens to build, about 3,000 tokens a year to keep and fix, and about 1 day elapsed. The change deletes no internal code.
