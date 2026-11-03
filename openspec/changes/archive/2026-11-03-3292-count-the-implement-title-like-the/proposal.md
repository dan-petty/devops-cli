# Proposal

## Why

The implement job of #3292 opens a pull request whose title the `Semantic PR title` check refuses. The check counts UTF-16 code units, and an emoji counts as two. The job counts code points and writes the title without a check, so a title that the job accepts fails CI after it has pushed the branch and spent tokens.

PR #3367 removed the cut from `delivery_title`, so the job keeps the whole summary (#3200). The remaining gap is that the job writes no title check of its own. The form check already holds the rule and its 60-unit limit.

## What Changes

- `src/devops_cli/roadmap/implement_run.py` checks the delivery title with `title_problems` before it creates or updates the pull request, and stops the item when the check refuses the title.
- The first check runs before the first push of a Planned item, so no branch stays on `origin` without a pull request.
- `tests/roadmap/test_roadmap_implement_job.py` gains a test: a title that the check refuses stops the item and writes no title.
- The `roadmap-implement-job` requirement that gives the delivery title states the whole summary, the 60 UTF-16 code units of the check, and the stop.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The pull request that delivers the code has the type of the issue

## Impact

- Code: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `openspec/specs/roadmap-implement-job/spec.md`
- Tests: `tests/roadmap/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_stage_title.py`

## Feasibility

- The probe of the cited path gives `delivery_title` is defined at src/devops_cli/roadmap/stage_change.py:794:def delivery_title(issue_title: str, declared: Collection[str]) -> str:`, so the function that the issue names is there.
- The code of `delivery_title` on `origin/main` returns `f"{head}: {safe_text(summary)}"`: it keeps the whole summary, because #3367 removed the cut that #3200 refused.
- The probe of the helper gives `title_problems` is defined at src/devops_cli/roadmap/pull_form.py:160:def title_problems(`, so the form check that the issue asks for already exists. `devops pr create` calls it and the implement job does not.
- The code of `src/devops_cli/roadmap/pull_form.py` shows `summary_length` counts a character above U+FFFF as two, the UTF-16 code-unit count of the check `Semantic PR title`.
- The code of `tests/roadmap/test_roadmap_stage_title.py` on `origin/main` shows `test_the_delivery_title_keeps_the_type_and_the_scope_and_the_whole_summary`, so the cut stays out and the check moves to the job.
- The code of `openspec/specs/roadmap-implement-job/spec.md` shows the requirement `The pull request that delivers the code has the type of the issue` with the text `at most 60 characters` and a scenario `A long summary`, so the text and its scenarios change together.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py`, then `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py`, then `uv run devops openspec check`.

## Existing Tool Considered

`title_problems` in `src/devops_cli/roadmap/pull_form.py` covers the need: it checks the form, the type, the scope and the length with `summary_length`. The change adds one caller in `_delivery_title`, one message and one test: roughly 20 lines, about 5000 tokens and half an hour. No parser and no text cut is added.
