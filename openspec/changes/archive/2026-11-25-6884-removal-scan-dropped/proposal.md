# Proposal: #6884

## Why
`find_removed_names` in `src/devops_cli/roadmap/stage/stage_removal_references.py` includes `drop`, `drops`, `dropped`, and `dropping` in `REMOVAL_VERBS`. Plans often say a step, rule, or behavior was "dropped" next to a backticked identifier such as `rewrite` without removing any code entity, causing false `removal-reference` findings in `devops roadmap stage` and `devops roadmap plan-recheck`. Closes #6884.

## What Changes
- Remove `drop`, `drops`, `dropped`, and `dropping` from `REMOVAL_VERBS` in `src/devops_cli/roadmap/stage/stage_removal_references.py`.
- Update `test_find_removed_names_handles_multiple_identifiers_and_verbs` and add regression tests in `tests/roadmap/stage/test_roadmap_stage_removal_references.py` covering `drop`/`drops`/`dropped`/`dropping` beside held test names and `deletes` still reporting unhandled test references.
- Update `openspec/specs/roadmap-stage/references/spec.md` to exclude the `drop` verb family from removal verbs.

## Capabilities
- `roadmap-stage/references`: Exclude `drop`, `drops`, `dropped`, and `dropping` from `REMOVAL_VERBS` while keeping `remove`, `delete`, `deprecate`, and `retire`.

## Impact
- `src/devops_cli/roadmap/stage/stage_removal_references.py` (reaches both `stage.py` and `plan_recheck.py`).
- `tests/roadmap/stage/test_roadmap_stage_removal_references.py`.
- `openspec/specs/roadmap-stage/references/spec.md`.

## Feasibility
Confirmed on `origin/main` (`a8e6e7c4a`): `REMOVAL_VERBS` in `src/devops_cli/roadmap/stage/stage_removal_references.py:34-37` contains `"drop"`, `"drops"`, `"dropped"`, and `"dropping"`. Both `stage.py:1305` and `plan_recheck.py:523` call `scan_removal_references`, which calls `find_removed_names`.

## Existing Tool Considered
Verb-based extraction of backticked identifiers in OpenSpec plan prose is internal to `src/devops_cli/roadmap/stage/stage_removal_references.py`; no external tool separates "dropped" step prose from code removal verbs. Editing `REMOVAL_VERBS` and tests removes the false positives with ~2k tokens and under 30 minutes of engineering work.
