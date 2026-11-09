# Proposal: #1335

## Why

Issue #1335 tracks Phase E for the infrastructure and planning packages.
The tracker coordinates moving test files onto shared edge fakes.
Six child issues delivered the code and test refactoring: #3744, #3746, #3748, #3749, #3751, and #3754.
All six children are merged into `origin/main`.
This change completes the tracker criteria and removes the remaining store references.

## What Changes

- Remove the remaining `memory_store` name occurrence in test function names (`test_roadmap_store_body_with_marks.py`).
- Verify that the target test files contain zero private imports from `devops_cli`.
- Verify that patch sites in the target test files remain confined to designated seams.
- Verify that `git grep -n -E "memory_store|roadmap_faults" -- src tests` returns zero matches.
- Archive the change folder for #1335.

## Capabilities

No new capability is added. This change verifies test modernization and completes a tracker issue.

## Impact

- `tests/roadmap/stores/test_roadmap_store_body_with_marks.py`
- OpenSpec planning artifacts for #1335
- No change to product code, CLI interfaces, or runtime behavior.

## Feasibility

- All six child pull requests (#3839, #3889, #4050, #3781, #3857, #3938) are merged into `origin/main`.
- `git grep -n -E "memory_store|roadmap_faults" -- src tests` yields zero occurrences after the test rename.
- AST scans confirm that the target test suites meet the acceptance criteria.
- Local test suites pass with zero regressions.

## Existing Tool Considered

The repository uses pytest, Hypothesis, and existing test double fakes in `tests/support/fakes/`.
No new third-party tool or dependency is needed.
