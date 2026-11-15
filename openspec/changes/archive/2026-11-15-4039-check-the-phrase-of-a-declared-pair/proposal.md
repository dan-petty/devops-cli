# Proposal

## Why

A plan that changes a prompt and its phrase test can quote the same rule with two texts: one in `tasks.md`, another in `proposal.md` or a spec scenario. The stage gates pass and the implementation then fails `test_the_prompt_and_the_document_keep_the_same_phrase_of_a_rule`, as pull request #3963 showed (#4039).

## What Changes

- Add `src/devops_cli/roadmap/plan_phrases.py`: `declared_phrases` reads each `("<document>", "<phrase>")` pair of `tasks.md`, and `phrase_problems` reports a code span that shares four consecutive words with a declared phrase and differs from it.
- Call it from `folder_problems`, so `devops roadmap plan-check` and the stage job report each phrase problem with the other problems.
- Add `tests/roadmap/test_roadmap_plan_phrases.py` for the declared pair, a divergent variant in the proposal and in a spec delta, an unrelated span and a plan with no pair.
- Name the check in `docs/roadmap/plan-check.md`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-plan-check`: the command reports the divergence of a declared phrase.

## Impact

- Code: `src/devops_cli/roadmap/plan_phrases.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_plan_phrases.py`
- Document: `docs/roadmap/plan-check.md`

## Feasibility

- Read on `origin/main`, 2026-11-14. `src/devops_cli/roadmap/plan_check.py:523:def folder_problems(` returns the problems of the change folder, and `:535:def staged_problems(` adds the title and body rules.
- The pair form is in the archived task `openspec/changes/archive/2026-11-07-3304-add-a-set-count-to-every/tasks.md:16`.
- The phrase test that fails is `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py:443`.
- `uv run pytest tests/roadmap/test_roadmap_plan_phrases.py tests/roadmap/test_roadmap_plan_check.py` passes after the change.

## Existing Tool Considered

`check_proposal` and `validate_change` check paths, forms and the spec delta, and neither compares quoted phrases. No open, maintained tool covers phrase consistency across the artifacts of an OpenSpec change folder. The change costs about 2,000 tokens to build and 200 a quarter to keep.

## Dependencies

None.
