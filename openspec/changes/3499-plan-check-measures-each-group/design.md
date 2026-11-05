# Design

## Decisions

- **Call `measure_groups` from `plan_check` with the groups that `read_change` gives.**: The stage job measures with this function, so one function gives one figure. The test compares the figure of `plan-check` with a call of `measure_groups` on the same plan.
- **Build the shared text with one function, `shared_texts`, that the stage job and `plan-check` both call.**: The shared text is the title and body of the issue and the files of the change folder. Two copies of that list can drift, and the figures would then differ with no test to show it.
- **Measure on the head commit of the pull request, in a detached worktree of `checkout_at`.**: `named_files`, `packed_file` and `rules_sections` read a directory, and the working tree of the caller can be at any commit or hold edits. The head commit is the tree that the plan names, and it is the same tree on each run.
- **Move `checkout_at` to `src/devops_cli/roadmap/clone_git.py` and give it the `operation` of its caller.**: `clone_git.py` already holds `git`. `plan_check.py` must not import an eval module for a git helper, and `stage_eval_run.py` and `stage_verify_eval.py` keep the same behavior.
- **Add `files` to `MeasuredGroup`.**: The measure already finds the files that the step packs. A second call of `named_files` in `plan_check.py` would repeat that work and could differ from it.
- **Read the budget with `load_settings().roadmap.stage.step_tokens`, and add no option.**: The issue names this setting. A person who needs another budget sets `DEVOPS_CLI_ROADMAP_STAGE_STEP_TOKENS`.
- **Report each finding as a problem with the rules `group-over-budget` and `group-no-files`, on the path `tasks.md` of the change folder.**: A problem has a path, a rule and a message, and the output and the exit code already follow from that.
- **Keep the one-line estimate of a created file.**: `tasks.md` holds no estimate, and the plan reader gives each created path one line. The figure of `plan-check` is then a lower bound for a group that creates files, and equal to the stage figure for any other group.
- **Record the size of the first request in `implement.spend`, under `steps`, from the `usage` of the first reply of the step.**: The reply reports the input tokens of the request that it answers, so the first reply gives the size of the first request. `implement.spend` is written apart from `implement.trace`, so the trace limit does not touch it.
- **Take the first request of the first turn of the first tier only.**: A later turn or tier continues a conversation, and its first request is not the first request of the step.

## Rejected alternatives

- **Measure on the working tree of the checkout that runs `plan-check`.**: The working tree is at any commit and can hold edits, so two runs on one pull request can give two figures. The test of equality with the stage job would then depend on the state of the checkout.
- **Check out only the named files and the routed documents.**: `rules_sections` reads the routes from `AGENTS.md` and the documents that they name. A second list of paths to extract can differ from what the step reads, and the full checkout of this repository takes about 1 second.
- **Add the estimate of created lines to `tasks.md`.**: This changes the `Changes:` line that the renderer, the reader, the path gates and the implement step all read, and plans on the default branch hold the old form. The issue does not name it. The limit is stated in the documents instead.
- **Add a `--step-tokens` option to `plan-check`.**: The issue asks for the setting of the stage job, and the variable already overrides it.
- **Put the first request in a `model` event of the trace only.**: `encode` drops the oldest events first, so a long run loses the first event. The record #2636 held 77 events and dropped 154.
- **Add the figure as a column of the table in the job comment.**: The table shows the totals of a step. The figure is a fact for a person who compares plan and model, and the record holds it.
