# Proposal

## Why

Issue #2772. The stage job wrote a plan for #2745 whose task groups name no files. The merged `openspec/changes/2745-config-files-and-their-copies-keep/tasks.md` shows three faults of the writer in `src/devops_cli/roadmap/stage_change.py`.

- Each group has the line `Reads: None.. Changes: None..`. The format `Reads: {reads}. Changes: {changes}.` and the text `None.` both end a sentence.
- `StageGroup.changes` and `StageGroup.reads` default to empty lists, so a reply may leave them out and still validate. The tasks of the group name `src/devops_cli/config/settings.py`, and the group names no file. `_packed_tokens` then packs nothing, so the budget check measures nothing.
- `StageGroup.documentation` accepts an empty string, so the task renders as `- [ ] 1.3 , run ...`.

## What Changes

- `StageGroup.changes` needs at least one path. `title` and `verify` need at least one character after the whitespace is stripped. `test`, `implementation` and `documentation` need at least one character that is no space and no full stop. A path holds no backtick and no control character, so it cannot break the line of its group. A reply that breaks a rule fails the schema, and the model gets the violation through the structured-reply retry of the proposal call. That retry runs once. A group with no `reads` stays valid.
- `StageGroup` has a new field `creates`: the paths of `changes` that do not exist yet. Every path of `creates` is also in `changes`.
- A group renders the line `Reads: <paths>. Changes: <paths>.` A group with no `reads` renders `Reads: none.`. A created path shows `(new)` after it. The type of a task text drops the full stops at its end, so no task holds `.,` and none starts with a comma.
- The stage job finds each `changes` path that is no file on the default branch and that no group creates. The stage comment on the issue names these paths in a warning line. The check never stops the item.
- The prompt `roadmap_stage_change.md` says that a group names at least one file in `changes`, names the files it needs in `reads`, lists a new file in `creates`, and gives every task a text.
- A consumer observes the comment and the plan files, so the change carries a spec delta. It modifies one requirement of `roadmap-stage` and adds two.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: the requirement "A staged item gets one comment and a record" now says that the comment names the paths that the plan changes and that exist nowhere. Two new requirements hold the rules of the reply and of the line.

## Impact

- `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- `tests/support/builders.py`, `tests/test_roadmap_stage_plan.py`, `tests/test_roadmap_stage_apply.py`.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The defects are real. `openspec/changes/2745-config-files-and-their-copies-keep/tasks.md` on `main` holds `Reads: None.. Changes: None..` in both groups and `- [ ] 1.3 , run` in both. `group_text` in `stage_change.py` formats `stage_group_files` (`"Reads: {reads}. Changes: {changes}."`) with `stage_none` (`"None."`), which gives the double stop.
- The schema accepts the reply that the model gave. `StageGroup.reads` and `StageGroup.changes` use `Field(default_factory=list)`, and the four texts are plain `str`. A faked reply with no `changes` and a blank `documentation` validates today.
- pydantic constrains the fields: `Field(min_length=1)` on a list, `StringConstraints(strip_whitespace=True, min_length=1)` on a string, and an `AfterValidator` on a task text. A reply that breaks one fails `model_validate` in `chat_structured` (`src/devops_cli/ai/client/structured.py`). That function sends the reply and the violation back to the model, up to `max_retries` times. The planner passes `max_retries=1`, so the model gets one correction. Then the function raises `StructuredOutputValidationError`, and `_failure_of` in `stage.py` stops the item with the class and the count of violations. The change reuses this retry and adds no second loop. The stop reason holds the count and not the field path, on purpose: `chat_structured` documents that its error carries "never a field path, since a path can be a key the model invented", because the message reaches spans and logs. The path goes to the model in the correction. So "the violation named" means the class and the count in the stop reason, and the field path in the correction request.
- No reader of the lines breaks. A search of `src/` for `Reads:` and `Changes:` finds only the writer. The implement step reads a group with `parse_task_groups` in `src/devops_cli/roadmap/implement_step.py`. That function takes the heading, the checkbox items and their code spans. It never parses the `Reads:` or `Changes:` paragraph, which stays in `TaskGroup.text` and goes to the model as it is. A plan written before this change, with `Reads: None.. Changes: None..`, is read as before.
- The stage job reads the clone at the default branch (`plan_stage` takes `source` "at the default branch"), and `_packed_tokens` already tests `is_file()` there. The new check uses the same test and the same `safe_resolve_subpath`.
- The first checks of the implementation: `uv run devops ci test tests/test_roadmap_stage_plan.py tests/test_roadmap_stage_apply.py`, each written to fail on `main` first.

## Existing Tool Considered

pydantic field constraints (`Field(min_length=1)`, `StringConstraints`) and the retry of `chat_structured`. The change builds no parser and no retry. The one small helper is the search for paths that exist nowhere. It is a loop of `is_file()` calls with the function `safe_resolve_subpath` that the module already uses, so no open tool covers it. Cost, estimated: about 40 lines of code, about 60k tokens of agent work to build and fix it, and one hour of elapsed time. The upkeep is small.

The change deletes the `or texts.stage_none` fallback for `changes` and the `.strip()` calls that the new field types make redundant.
