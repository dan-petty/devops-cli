# Proposal

## Why

The stage comment gives a token figure for each task group of a plan (#3499). The figure goes stale when the plan or the files that its tasks name change, and no gate measures it again. `devops roadmap plan-check` has no token measure. The implement step refuses a group only above the window minus the turn reserve, so a plan above the stage budget can start a run. The stage figures of four plans were 5150, 5687, 3798 and 31191 tokens. A measure of the same plans now gives about 25778, 12835, 60701 and 43832 tokens. No record holds the size of the first request of a step, so nobody can compare a stage figure with what the model received.

## What Changes

- `plan-check` measures each task group of the plan with `measure_groups`, the function of the stage job, on the tracked files of the pull request head. It reports a `group-over-budget` problem for a group above `roadmap.stage.step_tokens`, and a `group-no-files` problem for a group that changes a file that exists and packs no file. A group that only creates files packs none by nature, and the command accepts it.
- One function, `shared_texts` in `src/devops_cli/roadmap/stage_change.py`, builds the text that all groups share: the item and the files of the change folder. The stage job and `plan-check` both call it, so their figures stay equal.
- `MeasuredGroup` gains `files`, the number of files that the step packs for the group, so the stage job and `plan-check` count them in one place.
- `checkout_at` moves from `src/devops_cli/roadmap/stage_eval_run.py` to `src/devops_cli/roadmap/clone_git.py`, so `plan-check` can read the head commit as a checkout without a dependency on the eval.
- A step records the input tokens of its first model request. `implement.spend` holds them for each step under `steps`, apart from the trace, so the trace limit never drops them.
- The change carries a spec delta on `roadmap-plan-check` and on `roadmap-implement-job`, because the command output and the job record are behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-plan-check`: Plan-check measures each task group
- `roadmap-implement-job`: The record keeps the size of the first request of each step

## Impact

- Code: `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/clone_git.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/roadmap/stage_verify_eval.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/roadmap/plan-check.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`, `README.md`
- Tests: `tests/roadmap/test_roadmap_plan_check.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`, `tests/roadmap/test_roadmap_implement_step_trace.py`, `tests/roadmap/test_roadmap_implement_job_trace.py`

## Feasibility

- Read of `src/devops_cli/roadmap/plan_check.py`: the module has no call to `measure_groups` and no token count. `grep -rn measure_groups src` finds the callers `stage.py` and `implement_run.py` only. The premise of the issue holds.
- Read of `src/devops_cli/roadmap/stage_change.py`: `measure_groups(root, groups, shared=...)` counts the shared text, the text of the group, the files and the rules that the step reads under `root`, and 32 tokens for each estimated line of a created file. The stage job calls it with the item and the rendered files of the change folder.
- Read of `src/devops_cli/roadmap/implement_step.py`: the step refuses inputs above `window - CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS`, and no stage budget applies. The statement of the issue holds.
- Read of `src/devops_cli/roadmap/implement_trace.py`: `encode` drops the oldest events first, so the first model event of a long run is the first to go. A figure of the first request needs a place outside the trace.
- Command output: a script ran `read_change` and `measure_groups` over the 56 change folders of `origin/main`. 23 folders read, and 65 groups gave 2 groups above 40000 tokens, none above 64000 (the default of `roadmap.stage.step_tokens`), and 8 groups that pack no file. 6 of the 8 change an existing file that no task names in a code span, and 2 only create files.
- Limit that the plan format sets: `tasks.md` holds no estimate of the lines of a created file. The plan reader gives each created path one line, so the figure of `plan-check` for a group that creates files is lower than the stage figure by 32 tokens for each estimated line above the first. For a group that creates no file the two figures are equal. The proposal keeps the format: a change of the `Changes:` line is a change of the plan format, and the issue does not name it. The docs of the command state the limit.
- The deployed value of `roadmap.stage.step_tokens` is not in this checkout. The command reads the setting of the machine that runs it, so it uses the value that the deployment sets, 40000 or 64000.
- `uv run devops ci test tests/roadmap/test_roadmap_plan_check.py` and `uv run devops ci test tests/roadmap/test_roadmap_implement_job_trace.py` run the new tests and fail before the code and pass after it.

## Existing Tool Considered

Project code covers the need: `measure_groups`, `count_tokens`, `named_files`, `packed_file` and `rules_sections` give the figure, and `checkout_at` gives the head commit as a checkout. No outside tool knows the inputs of an implement step. The change reuses all of them and builds no counter. The cost is about 8,000 tokens to build, 1,000 tokens to keep and about 2 hours elapsed. The change deletes the copy of `checkout_at` in `src/devops_cli/roadmap/stage_eval_run.py` by moving it, and deletes no other code.

## Dependencies

The plan reader of #3482 reads a plan with no crash, so `plan-check` has a plan to measure.
