# Proposal

## Why

Issue #3262: a plan that the stage job writes gives the implement step no verification command. The stage job writes each task as `{work}, and verify that `{verify}` passes` (`stage_task_pass` in `src/devops_cli/lang/en/messages.py`, used by `_task_texts` in `src/devops_cli/roadmap/stage_change.py`), so the command is a code span in the first line of the task. The step reads a verification command only from a later line of a task that starts with `Verification:` (`_task_of` in `src/devops_cli/roadmap/step_files.py`). `TaskGroup.verification_commands` is empty for every group that the stage job wrote, and the step never runs the check of the group. The unticked-task check, the archive check and CI still run, so nothing else fails.

## What Changes

- The stage job writes the command of a task on its own line under the task, in the form that the parser reads and that `openspec/config.yaml` and the plans of #2742, #2585 and #2610 use:

  ```
  - [ ] 1.1 Write `test_x` in `tests/test_x.py`
    - Verification: `uv run devops ci test tests/test_x.py` fails on the base
  - [ ] 1.2 Change `src/devops_cli/x.py`
    - Verification: `uv run devops ci test tests/test_x.py` passes
  ```

  The messages `stage_task_test`, `stage_task_pass` and `stage_task_documents` change. `stage_task_process` does not change: a manual check has no command.
- The documents task becomes `{work}, and run `<regenerate command>``, with the line `Verification: `uv run devops ci docs` passes`.
- One new test file, `tests/roadmap/test_roadmap_stage_task_verification.py`, goes from a `StageGroup` through `group_text` and `render_change` to `parse_task_groups`, and compares `TaskGroup.verification_commands` with the `verify` of the group. It runs on each valid group of the golden set `tests/fixtures/roadmap_eval/stage` (60 groups, among them the five of the plan of #2175). It fails if the writer and the parser disagree.
- The tests that held the old text (`test_roadmap_stage_kind.py`, `test_roadmap_stage_plan.py` and its snapshot) hold the new text.
- The change folders that exist already are not rewritten. They are committed text, and the parser reads them as they are: the folders that the job wrote before this change keep the old form, and the step reads no command from them. A person or a later plan pass may rewrite one. This change does not.
- The requirement "A task group renders the tasks of its kind" of `roadmap-stage` is MODIFIED, because the text of a task is observable. It gains the sentence on the line `Verification:` and two scenarios.
- The change fits one pull request: one group, two source lines in one file and one test file.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A task group renders the tasks of its kind

## Impact

- Code: `src/devops_cli/lang/en/messages.py` (three messages).
- Tests (new): `tests/roadmap/test_roadmap_stage_task_verification.py`.
- Tests (changed): `tests/roadmap/test_roadmap_stage_kind.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/__snapshots__/test_roadmap_stage_plan.ambr`.
- Specs: `openspec/specs/roadmap-stage/spec.md` through the delta.
- Neighbours read and left as they are: `form_problems` and `path_problems` (`stage_form.py`, `stage_paths.py`) read the fields of `StageGroup`, not the rendered text. `check_proposal` reads the same fields. The model verification pass (`stage_verify.py`) reads the plan JSON, not `tasks.md`. `measure_groups` parses the rendered text with `parse_task_groups`; the verify command was a code span of the first line and is not any more, but `named_files` keeps only code spans that are existing files, and a command is none, so the files that a step reads do not change. `implement_strays` and `implement_eval` read the code spans of the whole text of a group, which still holds the command.
- Documents: none names the old text (`git grep -n -i "verify that\|fails on the base" -- docs README.md src/devops_cli/ai` finds no use of it).

## Dependencies

- #3263 (`stage_form.py`, `implement_shell_policy.py`): it decides which first words a verification command may have, for example `!` of a `! git grep` check. This change sends the command to the step as it is. The two do not touch the same lines.
- #3249 (`staging_title` in `stage_change.py`): another function of the same file. No shared line.
- Related: #3189, #3226, #3254. None of them MODIFIES the requirement of this delta (`git grep -n "renders the tasks of its kind" -- openspec/changes` finds only the archived change of #3005).

## Feasibility

Checked on `origin/main` e0de9ba1, on 2026-11-02, in a plain clone.

1. The defect reproduces. The test file of this change fails on the base: `pytest tests/roadmap/test_roadmap_stage_task_verification.py` gives `67 failed, 2 passed`. The first failure is `assert () == ('uv run devops ci test tests/test_sample.py',)` for a rendered behavior group. The two that pass are the count of the groups of #2175 and the group with a manual check, which has no command on either side.
2. The parser reads the nested form. `parse_task_groups` on `openspec/changes/2742-bound-the-number-of-prewarm-model/tasks.md` gives `('uv run devops ci test tests/ai/mcp/test_ai_prewarm.py ...', ...)` for group 1 and `('uv run devops docs check',)` for group 2. On `openspec/changes/2101-a-tool-run-names-the-repository/tasks.md`, which the stage job wrote in the old form, it gives `()` for groups 1 to 4.
3. The plan of #2175 has five groups, all of the kind `behavior`. Rendered on the base, `verification_commands` is `()` for each. After the change it is the `verify` of the group (`! git grep -n -w thinking_detected src/ tests/ docs/`, and `uv run devops ci` for the last).
4. Why the `Verification:` line and not the code span after "verify that". The parser, `docs`, `openspec/config.yaml` and the spec `roadmap-implement-step` ("The verification commands of a group SHALL be the code spans of the `Verification:` lines of its tasks") name the line. Reading the span after a phrase would put a second form into the parser, and a phrase in free text is the form that a model changes first. The writer is the only code that must change.
5. The line stays a list item of the task. In `_task_of`, `lines` are the inline tokens of a list item: the first is the task, the next ones are the nested items. A `Verification:` line in the same paragraph would be one inline token with the task, so it would not be read. The nested bullet is the form of the committed plans.

Not verified: a live stage run. The model writes `verify` as before; only the writer of the text changes.

## Existing Tool Considered

None covers it: this is one string in the writer of the project's own `tasks.md` and the parser of the project's own step. `markdown-it-py` already parses the file (`step_files.py`); the change adds no parser. Cost to build: about 25,000 tokens and about 40 minutes. Cost to keep: about 1,000 tokens each quarter, as the round trip test fails if either side changes alone. Cost to fix one miss: about 5,000 tokens. The change deletes the three phrases "and verify that" of the writer.
