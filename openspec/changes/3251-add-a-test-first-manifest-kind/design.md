# Design

## Decisions

- **Name the kind `manifest`, and keep `other` beside it.**: The kind names the artifact that the group changes, as `behavior` names a behavior. Many `other` groups change a manifest with no test, so only a group that creates or changes a case path takes `manifest`.
- **Reuse `test`, `implementation` and `verify` for a manifest group, and add no field.**: `src/devops_cli/roadmap/stage/stage_change.py:def group_text` already renders a `test` first with `fails on the base`, and the implement step already writes a failing case first for a group that has a test task.
- **Put the shape in the schema of `StageGroup` and the path rules in `form_problems`.**: A missing `test` reaches the model as one schema violation in the one retry, and a case path and a verify command name their problem in the text of the reply, beside the path rules that live in `form_problems`.
- **Tell a case path by its name, in `changes` or in `creates`, and read only `other` groups for it.**: The hand-written plan of #3173 changes a `_tests.yaml` file that already exists, and a behavior group keeps its own kind, so the rule refuses an `other` group and forces no behavior group.
- **Accept `uv run devops ci test` followed by a path of the group as the only verify command of a manifest group.**: The step runs the command, and the command takes a path of the group. The shell of the step runs no `promtool`, so no promtool command is accepted.
- **Keep the rule a pure function of the reply.**: The stage job has no sandbox and no mirror of the repository, and the replay reads no code and no git. The implement step shows the failure on the base when it runs the first task.
- **Take the replay case from the plan of #3173, whose group 5 changes a promtool case file with the kind `other`.**: The plan was written by hand before the kind existed, and the new rule refuses it, so the replay pins the rule on a real defect.

## Rejected alternatives

- **Name the kind `test-first`.**: The name states the form and not the artifact, so a second test-first form, such as a manifest with a case and a run, would need a third kind name.
- **Add a `case` field beside `test`.**: `src/devops_cli/roadmap/stage/stage_change.py:def _task_texts` and `src/devops_cli/roadmap/stage/stage_change.py:def _task_work_texts` read `test` for the failing task, so a second name would carry two copies of one rule in the prompt, the schema and the renderer.
- **Accept any `uv run devops` command as the verify of a manifest group.**: A group could give `uv run devops ci mutate` and run no case. The issue asks for a command that fails on the base, and `form_problems` holds the form of a verify command already.
- **Accept a `promtool` command pinned in `tools.lock` as the verify of a manifest group.**: The probes answer "The path `tools.lock` is no file at the root of the staging commit." and `src/devops_cli/roadmap/implement/implement_shell_policy.py` holds no `promtool` in `SHELL_PROGRAMS`, so the step's shell refuses the command.
- **Run the verify command in the stage job.**: The stage job has no sandbox and no mirror of the repository, and the replay of the golden set reads no code and no git.
- **Replace `other` with `manifest`.**: `src/devops_cli/roadmap/stage/stage_form.py` and the plans of the golden set hold `other` groups with a `verify` and no test, such as a deletion or a document, and the schema would refuse each one.
