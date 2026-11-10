# Design

## Decisions

- **Enter the `openspec_tool()` context once in `plan_implement`, around the selection, and pass the tool to `_Judge`.**: `plan_stage` opens the context once around its work, and the three production callers then get the tool with no edit of their own.
- **Run the validation after `check_proposal` returns no problem, on the mapping of change files that the gate already read.**: `check_proposal` reads the reply and starts no process, so the tool runs only on a plan that already passes the cheaper check, and no file is read twice.
- **Skip the validation when `openspec_tool()` yields None.**: The stage job skips it the same way at `src/devops_cli/roadmap/stage/stage.py:1698:if self._tool is None:`, so the two gates agree on a host without the binary.
- **Leave the item out with the first line of the problem as its reason, under the existing message `implement_left_plan`.**: `validate_change` joins one line for each issue, a left-out reason is one line of the report, and the text of `implement_left_plan` names the stage check, which is exactly the two gates that the implement gate now runs.
- **Catch `RoadmapStageError` and `ToolExecutionError` in the gate and return the first line of the error as the reason.**: `validate_change` raises both, and an uncaught error would stop the whole run instead of leaving one item out, which the issue forbids.
- **Validate the plan of a Staged item and of a Planned item.**: Both start a runner Job, and the model calls that the Job spends are the defect.
- **Keep the rule that a Staged item whose branch head holds only the archived change gets no plan check.**: The job archives a change only after the plan passed the stage gates, so there is nothing left to validate.
- **Answer the tool's commands on the `ProcessFake` that the job world already installs, and take the existing `openspec_fake` fixture in the three modules that plan without it.**: `src/devops_cli/openspec/tool.py:57:return run_subprocess(` sends the tool's run to the process runner, which the world fakes, so one shared fake answers the edge in each kind of test and no test builds its own double.
- **Add `script_validate` to the existing `OpenSpecFake` for a `validate <change> --strict --json` command that no `script` names.**: `tests/support/fakes/openspec.py:95:def script(` keys an answer by the exact argv, and the implement tests validate change folders of their own; a shape-keyed default keeps one fake and still lets a test script one change by name.
- **Give the three modules that plan without the world a small autouse fixture that scripts a passing validation, and answer the validation on any `ProcessFake` a test of those modules installs.**: The two fakes patch `shutil.which`, so the answer must not depend on which one wins; `answer_openspec` on the process fake makes either order pass.

## Rejected alternatives

- **Build a `fake_openspec` helper in `tests/support/roadmap_implement.py` that doubles `openspec_tool` and the tool's run.**: The project's test rule holds that each edge has one fake in `tests/support/fakes/<edge>.py` and that a test builds no double of an edge; the repository already has `tests/support/fakes/openspec.py:62:class OpenSpecFake:` and `tests/support/fakes/process.py:453:set_process_runner(fake)`, so the plan answers the edge with those.
- **Enter the `openspec_tool()` context once for each `judge` call.**: It sets up and tears down the isolated OpenSpec configuration for each item, and the issue asks for one context for a plan run.
- **Enter the context in the CLI command only.**: The Service and `devops roadmap explain` also reach `plan_implement` at `tests/support/roadmap_implement.py:518:return plan_implement(`, so they would get no tool.
- **Run the validation before `check_proposal`.**: It starts an `openspec` process for each item, including the items that the cheaper check refuses.
- **Leave every item out when `openspec` is not on PATH.**: The stage job stages a plan as unvalidated at `src/devops_cli/roadmap/stage/stage.py:1698:if self._tool is None:`, so the two jobs would disagree and an install without the binary would implement nothing.
- **Add a new message `implement_left_validate` for the reason of a refused plan.**: `src/devops_cli/lang/en/messages.py:2999:implement_left_plan: str = "Its plan fails the stage check: {problem}"` already names the stage check, and that check is `check_proposal` plus the OpenSpec validation, so a new message would change a second module and need a test of it for no gain.
- **Use the whole problem, cut to 2000 characters, as the reason.**: A left-out reason is one line of the plan report, and the extra lines would hide the other items of the plan.
- **Build a second validator in the implement module.**: `validate_change` exists at `src/devops_cli/roadmap/stage/stage_validate.py:def validate_change`, the stage job calls it, and a second copy would drift from `openspec/config.yaml`.
