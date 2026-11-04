# Design

## Decisions

- **Reuse `_is_test_module` to tell a test module from another path of a command.**: It is the one definition of a test module in the module, and a second regular expression would drift from it.
- **Judge only a `verify` command that names at least one test module, and skip a negative search.** A documentation command and a negative search prove their group by other means, and the issue limits the rule to a command that names a test. A `! git grep -n <literal> <path>` command searches for a name and runs no test, even when its path is a test module, so it is never judged.
- **Return one problem for each unnamed test module of a command.**: A command can run more than one test module, and the model needs the name of each module that is missing.
- **Judge a path against the group's own `changes`, `creates` and `reads`, and no other group's paths.**: The step of a group reads and changes only its own files, so a path of another group proves nothing about this one.
- **Put the problem text in `RoadmapMessages` in `src/devops_cli/lang/en/messages.py`, with the remedy.**: Every other stage form problem takes its text from the catalog and tells the model what to do. The model must know that it can list the module in `reads` or give the command of the group's own test.
- **State the rule in the staging prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md`, and assert it in `tests/roadmap/test_roadmap_stage_prompt_rules.py`.**: The retry problem is the second line of defense. The prompt is the first, and #3404 sets the same pattern for a new form rule.
- **Correct the `good-2491-a-refused-jwt-exchange-of-the` case in `changes`, not in its verdict.** Its `test` task updates `tests/github/test_github_app_identity.py`, so the recorded plan leaves out a file that the step changes. The fixture records the plan that the model should write, and that plan names the test.
- **Give the `_plan` helper of `tests/roadmap/test_roadmap_stage_form.py` a `verify` of the case's own test module.** The helper keeps the sample's `tests/test_sample.py` after a case changes another path, so the helper, and not the rule, is wrong.

## Rejected alternatives

- **Match `tests/**/test_*.py` with a new regular expression inside `form_problems`.**: `src/devops_cli/roadmap/stage_form.py` already holds `_is_test_module`, which requires the `tests` prefix, the `.py` suffix and the `test_` name prefix.
- **Judge every path under `tests/` that a command names.**: `_is_test_module` keeps a fixture, a helper and a `conftest.py` out of the rule, and `tests/roadmap/test_roadmap_stage_form.py` already asserts that such a file is not judged.
- **Judge every `verify` command, including `uv run devops ci docs` and `! git grep -n <name> src/ tests/`.**: `tests/roadmap/test_roadmap_stage_form.py` lists `uv run devops ci docs` and `! git grep -n -w old_name src/ tests/` among the accepted commands.
- **Judge only the first test module of a command.**: `tests/roadmap/test_roadmap_stage_task_verification.py` shows that a `verify` command is free text, so a command can name several modules.
- **Change the `good-2491` verdict to `acceptable`, or let the replay accept a good plan that the gate refuses.**: The verdict records a person's review of the plan. The plan is good, and only its `changes` list is wrong. A gate that accepts this plan also accepts a plan that runs a test it does not touch, which is the fault of #3427.
- **Accept a test module that imports or loads the source that the group changes.** A membership check cannot read the test, and the eval replay makes no model call. The name check is deterministic and catches the fault of the issue.
