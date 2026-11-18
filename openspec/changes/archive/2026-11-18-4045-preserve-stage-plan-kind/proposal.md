# Proposal

## Why

When a runner Job records `implement.pr` equal to `stage.pr`, `kind_of` returns `DraftKind.IMPLEMENT`.
Then `_judge_completeness` treats the stage plan pull request as an implementation draft.
Readiness checks then demand ticked task groups and refuse the stage plan pull request.
`devops pr check-readiness` fails with errors for all unticked task groups.
`stage_ready` and `devops pr ready` cannot mark the stage plan pull request ready.

## What Changes

- Pass the pull request title to `kind_of` from `read_draft`, `stage_ready`, and other callers.
- When `implement.pr` and `stage.pr` hold the same pull request number, use the title to resolve the conflict.
- Return `DraftKind.STAGE_PLAN` when the title starts with `docs(openspec): plan`.
- Return `DraftKind.IMPLEMENT` when the title does not start with `docs(openspec): plan` or when no title is given.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-merge-readiness`: Stage plan title wins a collision, Implement title keeps a collision as implement, Read draft preserves stage plan classification

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/roadmap/stage/stage_ready.py`, `src/devops_cli/roadmap/steps/fix_checks.py`
- Tests: `tests/roadmap/test_roadmap_draft_readiness.py`
