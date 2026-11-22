# Proposal: #6735

## Why

Issue #6735 names four defects that PR #6701 (#6633) left. The open step and the ready check do not measure the same text: `measured_body_text` splits the raw body, and `body_problems` splits `body.strip()`. Thus a body that starts with a blank line gets 1001 characters at open and 1000 at ready. The help text of `devops pr create`, its generated documents and the comment of `BODY_MAX_CHARS` still give the old meaning of the limit. The test module `tests/roadmap/stage/test_roadmap_stage_plan.py` imports `measured_body_text` at the top, so it does not collect on a base without that name, and one assertion uses the function under test as its oracle.

## What Changes

- `measured_body_text` splits `body.strip()` and ends the text at the first line that the form takes as the `Closes` or the `Plans` line. It is the one measure of the limit.
- `body_problems` and `plan_body_problems` give `_text_problems` the text of `measured_body_text`, so the open step, the form check of `devops pr create`, the ready check and the plan check measure one text.
- The help text of `devops pr create`, the generated `docs/commands/pr.md` and `docs/commands/gh.md`, and the comment of `BODY_MAX_CHARS` say that the limit measures the text above `Closes`.
- `tests/roadmap/stage/test_roadmap_stage_plan.py` imports no name of `pull_form` at the top, and its assertion compares with the known text.
- Two requirements of `pull-request-form` that still say "the body longer than 1,000 characters" say "the text above `Closes`".
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pull-request-form`: The open step and the ready check measure one text (added), The rules cut no text, devops pr describe refuses and prints nothing

## Impact

- Code: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/commands/pr.py`
- Documents: `docs/commands/pr.md`, `docs/commands/gh.md`
- Tests: `tests/roadmap/test_roadmap_pull_form.py`, `tests/roadmap/test_roadmap_plan_check.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`

## Feasibility

- A probe on the base a3e30286e with the body `"\n" + text + "\n\nCloses #5020\n\nChange: ..."` and a text of 1,000 characters: `open_body_problems` reports "The text above `Closes` has 1001 characters", `body_problems` reports no problem, and `measured_body_text` gives 1001 characters. The same text above `Plans` gives 1001 in `measured_body_text` and no problem in `plan_body_problems`.
- `grep -rn measured_body_text src tests` finds three readers: `open_body_problems`, `plan_check.py:283` and `tests/roadmap/stage/test_roadmap_stage_plan.py:39`.
- `grep` for `1,000 characters` finds the old text at `src/devops_cli/commands/pr.py:1380`, `docs/commands/pr.md:236`, `docs/commands/gh.md:1012` and `openspec/specs/pull-request-form/spec.md:114,147,162`.

## Existing Tool Considered

The alternatives check of 2026-11-22 gives the verdict none: the defects are in the help text, a comment, the measure and a test of this repository, and no open tool covers them. The change deletes the second measure, `"\n".join(lines[:closes_at])` in `body_problems` and `"\n".join(lines[:plans_at])` in `plan_body_problems`, and the `startswith` match of `measured_body_text`.
