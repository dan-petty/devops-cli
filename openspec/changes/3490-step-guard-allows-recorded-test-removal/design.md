# Design

## Decisions

- **Reuse the class `tests_lost` and change its action to `wait` in `ACTION_BY_CLASS`, and add no class.**: The step passes this class since #3476, so the stop no longer reads `ci_infra`. A stop for a test that the plan does not record needs a person: a new image cannot restore the test.
- **The record counts only on `origin/<default>`.**: AGENTS.md rule 5 lets only the owner lower a threshold, and only a person merges a pull request. So a person allows a removal when that person merges the plan. The job reads the record the way `_hooks_config` reads the hooks, so an entry that the agent writes on its branch waives nothing.
- **An item whose plan is only on its staged branch has no record.**: Nobody merged that plan, so each lost test stops the step.
- **`read_change` fills `StageProposal.weakened_checks`, and `merged_recorded_tests` reads only `proposal.md`.**: The gates read the whole plan. The guard needs one section, and a defect in another file of the plan must not change the guard.
- **The form of an entry is one bullet: `- **<check>**: Stopped: <stopped> Safeguard: <safeguard>`.**: The design file uses the same `**name**: reason` bullet, and `_bullets` reads one line for each bullet. The texts live in `MESSAGES.roadmap` as `stage_weakened_checks_title` and `stage_weakened_entry`, so the writer of #3320 and the reader use one form.
- **The reader refuses a line of the section that is not an entry.**: A lost entry would turn a removal that a person allowed into a stop, and a wrapped entry would lose its safeguard. The plan check reports the file before the merge. A section that reaches the default branch in another form stops the item with `plan_defect`.
- **An entry names a test as `path::name` in its `check`, and one entry can name more than one test.**: `lost_since` gives the path and the qualified name, so the match is exact. The plan of #3320 asks that the `check` holds the name of the deleted test, and `path::name` holds it.
- **A file path alone in a `check` waives nothing.**: A path would waive each test that a later commit adds to the file.
- **The field is `SkipJsonSchema` in the reply model.**: The stage job cannot write the section yet, so the model must not see a key whose value the job would lose. #3320 shows the key when it adds the writer. The test of the reply keys reads the schema, which is what the model sees.
- **`run_step` takes `recorded_tests`, and the default is none.**: The step holds no knowledge of the default branch, and the same holds for `hooks`. The command `devops roadmap implement step` passes none, so a step that a person runs by hand refuses each lost test.
- **`load_case` adds the record to `allow_lost_tests`, and `run_case` gives that list to the step.**: The property and the step of a fixture then read one list. A fixture clone has no remote, so it cannot read `origin/<default>`, and the fixture is the trusted input.

## Rejected alternatives

- **Add a class `lost_test` with the action `stop`.**: `FailureAction` has no `stop`, and `tests_lost` already names the cause. The docstring of `failure.py` says that the class list is fixed.
- **Read the record from the `proposal.md` of the checkout.**: `implement_step.py` commits each file that the agent writes, also `proposal.md`, so the agent could waive any test. `_restore_tasks` protects only `tasks.md`.
- **Read the record at the start of each step from the checkout.**: A `wip:` commit of an earlier step can hold an edit of the agent, and the next step starts from it.
- **Wait for #3320.**: Its implement job stopped because no group reads the section back.
- **Show the field in the reply schema and leave the writer to #3320.**: `test_the_top_level_keys_of_the_reply_are_the_fields_of_the_proposal` then asks for a key in `roadmap_stage_change.md`, and `_proposal_file` would drop what the model gives.
- **Keep the reader out of `StageProposal`.**: `check_proposal` reads the plan through `read_change` in `plan_check.py`, `plan_recheck.py` and `implement.py`. The gate of #3320 would refuse each plan whose record the reader dropped.
- **Delete `allow_lost_tests` and read only the plan.**: 14 fixtures hold the field, and their plans are old plans with no section. The issue asks for the same list, not for a new one.
