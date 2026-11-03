# Proposal

## Why

Two small form defects pass the plan gates (#3255). A group whose first task is one bare filename, such as `src/devops_cli/roadmap/stage_form.py`, passes `form_problems`, and the task says nothing to the implement step. A title such as `plan #2950 plan alternatives coverage telemetry` passes `title_problems`, and a person reads a repeated word in the log. Each one cost a review round in the plan fixes of 2026-11-02.

## What Changes

- `form_problems` refuses a `test`, `implementation` or `documentation` text of a group that holds one word or less. A code span counts as one word, so a path alone, a word alone and a code span alone are refused. The problem names the group by its number and title and the part.
- `title_problems` refuses a summary that starts with `<word> #<number>` and then repeats that word as its first word (`plan #2950 plan ...`), and a summary that repeats the issue number. A later use of the word is not judged.
- The change observes new behavior of two gates, so it carries a spec delta.
- The ready mark of a plan that holds a placeholder group (item 3 of the issue) is not part of this change. The refine step moved it to #3297, and the content gate of #3200 owns the placeholder text. A comment on #3200 carries the rule.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A task of a group holds more than one word
- `pull-request-form`: A plan title repeats no word and no issue number

## Impact

- Code: `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_stage_form.py`, `tests/roadmap/test_roadmap_pull_form.py`
- Documents: `README.md` is unchanged, because no command or option changes.

## Feasibility

- `git grep -n "def form_problems" src/` shows `src/devops_cli/roadmap/stage_form.py:91`, and its body checks the `verify` command and the new test paths only. A group with `test` set to `tests/roadmap/test_stage.py` gives no problem. A test on the base commit shows it: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` fails with `not enough values to unpack (expected 1, got 0)`.
- `git grep -n "def title_problems" src/` shows `src/devops_cli/roadmap/pull_form.py`, and `_summary_problems` checks the length, the cut and the placeholder only. The same run on the base commit fails for the title `docs(openspec): plan #2950 plan alternatives coverage telemetry`.
- The first task of a behavior group is the `test` text: `_task_texts` in `src/devops_cli/roadmap/stage_change.py` renders `stage_task_test.format(test=group.test, ...)`. So a gate on the `test` text is a gate on the first task.
- The refine design of the issue asks to refuse a repeated `plan` word anywhere after the prefix. The merged titles `docs(openspec): plan #3200 Refuse placeholder and cut plan text` (#3260) and `docs(openspec): plan #3344 Refuse a plan that reads an absent model field` (#3350) hold that word later in the summary. The acceptance criteria of the issue ask for the leading repeat only, so this change refuses the leading repeat and the repeated number, and a test keeps both titles valid.
- `git grep -n "title_problems" src/` shows two callers: `devops pr create` (`src/devops_cli/commands/pr.py`) and `build_title`. The stage job calls neither: `staging_title` builds its title with no form check. So the new title rule guards `devops pr create` and `devops pr describe`, and not the staged plan title. The open issue #3215 holds that gap: the jobs then build and check their title with `pull_form`.

## Existing Tool Considered

No open, maintained tool knows this plan form. A markdown linter such as markdownlint checks files and not the text of a model reply, and it cannot name a group of a plan. The change extends `form_problems` and `title_problems`, which the stage job and `devops pr create` already call. Cost to build: about 25k tokens and 1 hour. Cost to keep: two small functions, three messages and their tests, about 5k tokens a year. Cost to fix: the word count has no grammar, so it needs no word list. The change deletes no internal code.
