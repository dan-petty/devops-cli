# Design

## Decisions

- **Put the `retitle` row in `MODEL_LANE_ROWS`.**: The row calls a model, and the model lane holds the rows that call one.
- **Put the row after `refine` and before `stage`.**: The stage job applies a title rule, so the titles must be written before the stage job reads them in the same round.
- **Set the interval to 61 minutes.**: The delay of the title rule stays near one hour, and the model runs less often than the stage interval of 37 minutes.
- **Pass `build_retitle_model()` to `plan_retitle`.**: `plan_retitle` takes a `RetitleModel`, and `build_retitle_model()` is the model of the command. The `get_task_model` call returns a pydantic-ai model that the job cannot use.
- **Pass `DEFAULT_ROADMAP_RETITLE_LIMIT` as the limit.**: The limit bounds the spend of a round to 25 model calls.
- **Take no clone.**: `plan_retitle` and `apply_retitle` read and write the store only.
- **Add `include_retitle` to `build_stub_table`, default `"retitle" in runners`.**: The other optional rows use the same rule, and the stub tables of existing tests keep their rows.

## Rejected alternatives

- **Call `get_task_model("background")`.**: The result is a pydantic-ai `Model`, and `plan_retitle` calls `model.summarize`. The settings define no `background` task.
- **Put the row after `stage`.**: The stage job would leave out the items with a long title for one more round.
- **Include the row in every stub table.**: Tests that assert the row set of a stub table would fail.
