# Proposal

## Why

The implement step reads every code span of a `Verification:` line as a command (#3596). `_task_of` in `src/devops_cli/roadmap/step_files.py` collects them all. A code span that is prose, such as `tagged_image` in the plan of #2610, is then refused as a program that is not in the allowed list, and the step stops the group. #3595 removed the 13 refused spans of the active plans by rewriting those plans. That fix keeps the cause: the next plan with a prose code span stops its step again.

## What Changes

- `_task_of` reads as a command only a code span of a `Verification:` line that starts with `$ `. It removes the mark, and it keeps every other code span as prose. The mark is the shell prompt that documents use for a command line, so a reader needs no new rule. The docstring of `_task_of` states the rule.
- A line with no marked span gives the group no command. The project keeps no old form before `1.0.0`, so there is no fallback to the first span or to the allowed program list.
- The stage templates `stage_task_test`, `stage_task_pass` and `stage_task_documents` write the mark, and so does the task that the plan amendment adds (`implement_amend`).
- The active plans, the test fixtures and the snapshots that hold a `Verification:` line are written again with the mark. The rule for plans in `openspec/config.yaml` and the text of the `plan-recheck` document name the mark.
- `devops roadmap plan-recheck` counts a folder as unverified when it has no marked command, and its mechanical rewrite adds a marked line to a group with none. A merged plan in the old form gets that line from the rewrite.
- The change alters what the implement step observes, so it carries a delta for `roadmap-implement-step` and `roadmap-stage`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: the verification commands of a group are the marked code spans.
- `roadmap-stage`: the stage writes the mark.

## Impact

- Code: `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/implement_amend.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/plan_rewrite.py`, `src/devops_cli/roadmap/plan_recheck.py`.
- Tests: `tests/roadmap/test_roadmap_step_files.py` (new) and the tests, snapshots and support files that write a `Verification:` line.
- Plans: the `Verification:` lines of the active `tasks.md` files get the mark. Their owners rebase onto this change. A plan on a branch that does not hold the mark has no command until `plan-recheck` rewrites it or its owner adds the mark.
- Documents: `openspec/config.yaml` and `docs/roadmap/plan-recheck.md`.

## Feasibility

- Command output at `origin/main` confirms the premise. `_task_of` takes `_code_spans(line)` of each `Verification:` line without a filter, and `verification_problem("tagged_image")` returns the reason that the program is not in the allowed list. #3595 (merged as #3809) rewrote the plans so that no span is refused, and it added the invariant test; it did not change `_task_of`. #3482 changed the plan reader only. So neither covers this issue.
- `markdown-it-py`, already a dependency, gives the code spans of the line. No tool reads a `Verification:` line or tells a marked span from prose.
- The plan reader (`plan_read._task`) reads `task.verification[0]`, and `_verification_suffixes` reads the text after the second backtick, so both work with the mark. `FAILS_ON_BASE` reads the text after the last backtick of the template, which the mark does not change.

## Existing Tool Considered

No open, maintained tool or library covers the need: the rule is the plan format of this repository. The change builds about 10 lines in `_task_of`, plus the template and fixture edits. Cost: about 40,000 tokens to build (most of it the fixture edits), about 2,000 tokens a year to keep, and about 3 hours. It deletes the read of unmarked spans as commands.
