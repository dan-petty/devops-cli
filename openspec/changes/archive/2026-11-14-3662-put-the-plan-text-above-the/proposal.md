# Proposal: #3662

## Why

`devops pr create` refuses a plan body that follows CONTRIBUTING.md section 4. The document says that a plan body has the line `Plans #<issue>` in place of `Closes`, and a delivery puts its text above `Closes`, so a reader puts the plan text above `Plans`. `plan_body_problems` reads the text only between `Plans` and `Change:`, finds nothing, and refuses the body with a message that names `Closes`. The form, the document and the message disagree. Closes #3662.

## What Changes

- `plan_body_problems` reads the plan text above the `Plans` line, as the delivery form reads its text above `Closes`.
- The short-text message of a plan body names `Plans` and says the text goes above it. The delivery message still names `Closes`.
- `build_plan_body` writes `why`, then `Plans #<issue>`, then `Change:`.
- CONTRIBUTING.md section 4 and the docstring of `plan_body_problems` state the order.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/round`: A plan body puts its text above the `Plans` line.

## Impact

- Code: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `CONTRIBUTING.md`
- Tests: `tests/roadmap/test_roadmap_pull_form.py`, `tests/roadmap/stage/test_roadmap_stage_apply.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`

## Feasibility

Read on 2026-11-14 against `origin/main` at `04107728d`.

- The form reads the wrong range: `src/devops_cli/roadmap/pull_form.py:314:_text_problems("\n".join(lines[plans_at + 1 : change_at]), ...)`.
- The message names `Closes`: `src/devops_cli/lang/en/messages.py:1627:form_body_short`.
- The builder writes the old order: `src/devops_cli/roadmap/pull_form.py:399:body = f"Plans #{issue}\n\n{why.strip()}\n\nChange: ..."`.
- The document states the old order: `CONTRIBUTING.md:176`.
- The new tests pass on the branch: `uv run devops ci test tests/roadmap/test_roadmap_pull_form.py tests/roadmap/stage`.

## Existing Tool Considered

The form is an existing check of this repository, and no open tool covers a pull request body form. The change moves one slice of lines and adds one message, about 20 lines of code and 40 lines of tests.
