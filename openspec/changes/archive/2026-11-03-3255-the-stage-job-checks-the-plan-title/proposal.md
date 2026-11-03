# Proposal

## Why

The first fix for #3255 added the repeat rule to `title_problems`, and `devops pr create` runs it. The stage job does not: `staging_title` builds `docs(openspec): plan #<number> <summary>` from the model summary, and `StageProposal` accepts a summary such as `plan the form of a task`. So the title `docs(openspec): plan #3255 plan the form of a task` is still written. Four such titles are on main (#2972, #2986, #3089, #3225). The rule also misses a repeat that has a colon after the number, two spaces before it, a word before the word, a hyphen word or a dash before the text. This change closes the live hole and the cheap evasions.

## What Changes

- `_settle` in `src/devops_cli/roadmap/stage.py` runs `title_problems` on the staged title. A problem goes back to the model once, as every other refused reply does, and a second refusal stops the item.
- The stage prompt tells the model to start the summary with a verb other than `plan` and to write no issue number in it.
- The lead pattern of `title_problems` reads ASCII digits only, and finds the word before the number when other words, extra spaces, a colon or a dash stand around it.
- The tests kill three mutants that the review of the first pull request found: the code-span word in the task gate, the edge strip of the first word, and the digit lookahead of the number check.
- Known limit: the task gate counts words, so a text of two paths passes. No grammar is built.
- The change alters what the stage job accepts, so it carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pull-request-form`: A title repeats no word and no issue number
- `roadmap-stage`: The stage job checks the form of the plan title

## Impact

- Code: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_pull_form.py`, `tests/roadmap/test_roadmap_stage_form.py`

## Feasibility

- `staging_title(3255, "plan the form of a task")` returns `docs(openspec): plan #3255 plan the form of a task`, and `title_problems` of that title returns the repeat problem (run on main at ed77fe8a). `git grep -n title_problems src/` shows `src/devops_cli/commands/pr.py` and `pull_form.py` only, so the stage job runs no title check.
- The issue #3215 asks the stage and implement jobs to build all pull request text with `pull_form`, a larger change that adds a plan body form. This change does the one call that closes the hole now: `title_problems` on the staged title. It builds nothing that #3215 must undo, because #3215 calls the same function.
- The check of the `git log --all` subjects (799 unique) with the new pattern refuses only the five titles of the form `plan #N plan ...`. No other subject is refused.
- Each of the three mutants fails at least one new test.

## Existing Tool Considered

No open, maintained tool checks a plan title against this repository's form. The change reuses `title_problems` and the retry path of `_settle`. Cost to build: about 20k tokens and 1 hour. Cost to keep: one call and one pattern, about 3k tokens a year. The change deletes no internal code.
