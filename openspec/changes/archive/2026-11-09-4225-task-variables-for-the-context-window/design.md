# Design

## Decisions

- **A second tuple, `_TASK_WINDOW_VARIABLES = ("context_window", "max_tokens")`, beside `_TASK_VARIABLES`.**: The generator names a variable from a field of the task model, so the tuple is the whole change. `analysis` and `stage` use both tuples. `verification` uses the second one only, because the issue asks for the window and the reply limit of that task and for nothing else.
- **The window variables go on the tasks of the issue and not on every task.**: The issue names `stage`, `analysis` and `verification`. A variable for a task that nobody asked for adds a name to keep and to document.
- **No new check on the value.**: `AITaskOverride` declares `gt=0` for both fields, and an invalid value already fails with the name of its variable. A test pins that.

## Rejected alternatives

- **Set the window in `config.yaml` for each baseline run.**: Rejected by the evidence of #3566: the deployed value stays, and a live change of the stage window is a separate decision.
- **One variable for all tasks.**: Rejected: `AIConfig.context_window` already is the global value, and the baseline must move the window of one task and leave the others. `tests/config/test_ai_task_settings_paths.py` pins that the stage variable does not move `analysis`.
- **Give `verification` the four existing fields too.**: Rejected: no issue asks for them. A later issue adds them with the same tuple.
