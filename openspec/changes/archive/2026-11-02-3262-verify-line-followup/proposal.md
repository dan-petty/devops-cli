# Proposal

## Why

Issue #3262, follow-up of the first change (the stage job writes a `Verification:` line under a staged task). A review of that change found two faults that it opened, and three smaller ones.

1. A line break in a text of a group adds a `Verification:` line. `test`, `implementation`, `documentation` and `title` are not on one line, and `verify` is not either. The step reads every `Verification:` line of `tasks.md` and runs it if its first word is on the shell list (`git`, `uv`, ...). The gate (`form_problems`) checks only `verify`. The planner is a model that reads the text of an issue, so a text of an issue could add a command that no gate looked at. A line break in the `reason` of a criterion has the same reach: it can add a group.
2. Merge order with #3269 (the step runs `! git grep`). That change is merged now, so the point is to prove that the groups of the golden set run.
3. A backtick in `verify` ends the code span, so the step gets half a command or none.
4. The first change said that `openspec/config.yaml` documents the `Verification:` line. It did not.
5. The spec delta of the first change dropped the sentence "An `other` group SHALL render no test and no words "fails on the base"" with no note.

## What Changes

- `Text` and `Sentence` in `src/devops_cli/roadmap/stage_change.py` fold their value to one line (`_one_line`, as `Process` does). So `title`, `test`, `implementation`, `documentation` and `verify` hold no line break, and the writer can emit only the `verify` of the group and the check of the documents as `Verification:` lines. The `reason` of a criterion is folded when it is written, as the `criterion` already is.
- `form_problems` refuses a `verify` command with a backtick, with its own sentence (`stage_problem_verify_backtick`).
- `openspec/config.yaml` says in the rule for tasks that a verification command goes on a nested line `Verification:` with the command in a code span. This is the place where the claim of the first change is now true.
- The sentence of finding 5 returns as a clause of the scenario "A deletion that keeps behavior": the text of the requirement must stay under 500 characters, and a longer text makes `openspec validate --strict` warn. The scenario is the place where a test asserts it, and `test_an_other_group_renders_no_test_and_no_failure_on_the_base` does.
- The golden set test now also asks the shell policy of the step (`verification_problem`) about each command of the 60 groups. It passes on the base of this change, as #3269 is merged: it is a guard, not a fix.
- Spec delta for `roadmap-stage`: two ADDED requirements ("A text of a group stays on one line", "A verify command holds no backtick") and the MODIFIED requirement "A task group renders the tasks of its kind", whose scenarios change.
- The change fits one pull request: three small edits in three source files and one test file.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A text of a group stays on one line, A verify command holds no backtick, A task group renders the tasks of its kind (MODIFIED)

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/lang/en/messages.py` (one message).
- Tests: `tests/roadmap/test_roadmap_stage_task_verification.py` (changed).
- Documents: `openspec/config.yaml` (one rule). The spec `openspec/specs/roadmap-stage/spec.md` through the delta.
- Fields that reach `tasks.md`, all checked: `title`, `test`, `implementation`, `documentation`, `verify` (folded here), `process` (folded already), `reads`, `changes`, `creates` (`_repository_path` refuses a control character and a backtick), and the `criterion` (folded) and the `reason` of a criterion (folded here). Texts that go to `proposal.md` and `design.md` are no part of the task list, and the parser reads only `tasks.md`.

## Dependencies

None open. #3269 is merged. The first change is merged.

## Feasibility

Checked on `origin/main` f082d5c3, on 2026-11-02, in a plain clone.

1. Finding 1 reproduces. With a `BREAK` of `\n  - Verification: `git push origin HEAD`\n` in a field, the new tests fail on the base for `title`, `test`, `implementation`, `documentation` and `verify`: `verification_commands` holds `git push origin HEAD` and `form_problems` says nothing. The field `process` passes, as it is folded already. A `reason` of a criterion with `\n\n## 2. Extra\n\n- [ ] 2.1 ...` adds a group 2 with the command.
2. Finding 2: with #3269 merged, `verification_problem` gives `None` for each command of the 60 groups of the golden set, among them the four `! git grep` groups of #2175. The guard test passes on the base of this change.
3. Finding 3 reproduces: `uv run devops ci test ``x``` and `uv run devops ci test `x`` passed `form_problems` with no problem on the base. The `! git grep -n '`foo`' src/` case was refused already by #3269, but with the reason of the negative-search shape and not the backtick.
4. Finding 4: `git grep -n "Verification:" -- openspec/config.yaml docs` found nothing on the base. Only `step_files.py` and the spec `roadmap-implement-step` name the line.
5. Folding the fields cannot change a valid plan: a text that has a line break in it was never a good task text, and `Process` has folded since #3005. The golden-set round trip (60 groups) still passes.

Not verified: a live stage run with a model, and a step run with the folded text.

## Existing Tool Considered

None covers it: this is the schema of the project's own reply and its own gate. `pydantic` validators already do the folding (`AfterValidator`), as `Process` uses them. Cost to build: about 20,000 tokens and about 30 minutes. Cost to keep: about 1,000 tokens each quarter; the round trip tests fail if a text can add a command again. The change deletes nothing.
