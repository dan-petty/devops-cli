# Proposal

## Why

The implement job of #3292 opens a pull request whose title the `Semantic PR title` check refuses, because `delivery_title` counts code points and the check counts UTF-16 code units. An emoji counts as one in the job and as two in the check, so a title that the job accepts fails CI and the item stops.

## What Changes

- `delivery_title` in `src/devops_cli/roadmap/stage_change.py` measures the summary with `summary_length` and cuts it at 60 UTF-16 code units on a code point boundary.
- `tests/roadmap/test_roadmap_stage_title.py` gains a delivery title test with emoji and a test at the exact 60-unit bound.
- The `roadmap-implement-job` requirement that gives the delivery title states the limit as 60 UTF-16 code units.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The pull request that delivers the code has the type of the issue

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`
- Documents: `openspec/specs/roadmap-implement-job/spec.md`
- Tests: `tests/roadmap/test_roadmap_stage_title.py`

## Feasibility

- The probe of the cited path gives `delivery_title` is defined at src/devops_cli/roadmap/stage_change.py:714:def delivery_title(issue_title: str, declared: Collection[str]) -> str:`, so the function that the issue names is there.
- The probe of the helper gives `summary_length` is defined at src/devops_cli/roadmap/pull_form.py:42:def summary_length(text: str) -> int:`, so the count that the issue asks for already exists.
- The code of `src/devops_cli/roadmap/pull_form.py` shows `return len(text) + sum(ord(char) > 0xFFFF for char in text)`, the UTF-16 code-unit count of the check `Semantic PR title`, and its callers list in the context shows `stage_change.py` already uses it for `staging_title` and no line for `delivery_title`, which is the gap of #3292.
- The code of `tests/roadmap/test_roadmap_stage_title.py` shows `test_the_delivery_title_keeps_the_type_and_the_scope_and_cuts_the_summary_at_a_word`, which asserts `len(summary) <= SUMMARY_MAX_CHARS` in code points and that the summary ends with `...`, so the cut stays and only its measure changes.
- The code of `openspec/specs/roadmap-implement-job/spec.md` shows the requirement `The pull request that delivers the code has the type of the issue` with the text `at most 60 characters` and the scenario `A long summary` with 80 characters, so the text and that scenario change together.
- The docstring of `src/devops_cli/roadmap/pull_form.py` states that `tests/invariants/test_workflow_contracts.py` holds the workflow's summary pattern and its scope list equal to `SUMMARY_MAX_CHARS`, so that invariant file is the one that ties the pattern to the constant.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py`, then `uv run devops ci test tests/invariants/test_workflow_contracts.py`, then `uv run devops openspec check`.

## Existing Tool Considered

`summary_length` in `src/devops_cli/roadmap/pull_form.py` covers the need: it counts a text as the JavaScript check `^.{1,60}$` counts it. The change adds a caller in `delivery_title` and cuts the summary on a code point boundary. That is about 10 lines of code, two tests and one requirement text: roughly 10000 tokens and half an hour. No internal code is deleted.
