# Proposal

## Why

`devops roadmap retitle` (#3486) shortens the long title summary of open items, but no Service row runs it. A person or an agent must run it by hand, so a new long title waits until someone does. The stage job leaves out an item with such a title (#3535).

## What Changes

- `src/devops_cli/roadmap/run.py` gains a model-lane row `retitle`, after `refine` and before `stage`, so the stage job reads the shortened titles in the same round.
- The row runner calls `plan_retitle` with the model of the retitle job and `DEFAULT_ROADMAP_RETITLE_LIMIT`, then calls `apply_retitle` with the plan.
- `src/devops_cli/config/defaults.py` defines `DEFAULT_ROADMAP_RETITLE_INTERVAL_MINUTES` as 61.
- The row is due on a first run and after its interval, and the Service records its last success in `schedule.json` as for the other rows.
- `build_stub_table` gains `include_retitle`, which defaults to `"retitle" in runners`, so the stub tables of the existing tests keep their rows.
- The `roadmap-retitle` capability gains requirements for the row, because the Service behavior is observable.
- `CONTEXT.md`, `docs/roadmap/intake.md` and the docstring of `run.py` name the new row.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-retitle`: A Service row runs the job

## Impact

- Code: `src/devops_cli/roadmap/run.py`, `src/devops_cli/config/defaults.py`
- Tests: `tests/roadmap/test_roadmap_retitle.py`
- Documents: `CONTEXT.md`, `docs/roadmap/intake.md`

## Feasibility

- The premise holds. `src/devops_cli/roadmap/run.py` holds `MODEL_LANE_ROWS` with the rows `refine`, `stage` and `alternatives`, and no `retitle` row. `grep -rn retitle src/devops_cli/roadmap/run.py` returns nothing.
- `plan_retitle(store, *, repo, model, item_number=None, limit=None)` and `apply_retitle(store, plan)` in `src/devops_cli/roadmap/retitle.py` take the store and no clone path, so the row needs no clone.
- One detail of the issue differs from the code. The issue says the runner passes "the background model" from `get_task_model("background")`. That call returns a pydantic-ai `Model`, and `plan_retitle` takes a `RetitleModel`, an object with `summarize(request)`. The settings hold no `ai.tasks.background` task either. The retitle job builds its model with `build_retitle_model()`, which uses the `triage` task client, and `docs/roadmap/intake.md` states that. The row passes `build_retitle_model()`, the same model as the command, so the row and the command give the same titles. This is a build detail, not a block.
- The check of the change is `uv run devops ci test tests/roadmap/test_roadmap_retitle.py tests/roadmap/test_roadmap_run.py`.

## Existing Tool Considered

No open, maintained tool covers a row in this repository's due table. The change adds one `JobRow` in the same way as the rows of the other jobs, and deletes no code. The written cost is about 6,000 tokens to build, 1,500 tokens to keep and 3,000 tokens to fix, and about half a day.

## Dependencies

None.
