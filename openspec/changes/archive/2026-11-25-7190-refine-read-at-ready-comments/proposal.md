# Proposal: #7190

## Why
`src/devops_cli/roadmap/refine/refine.py:3493` calls `_repeated_at(item)` inside `_has_trusted_comment_since_last_round` (#7190). Commit `44fb86a04` (#7144, closes #6371) removed `_repeated_at` and replaced it with `_read_at(item)` (`RefineRecordKey.READ_AT`), while commit `3bb8a4891` (#7178, closes #6452) merged after `44fb86a04` and introduced `_has_trusted_comment_since_last_round` still calling `_repeated_at`. That leaves `main` failing `lint`, `typecheck`, `uv-check`, and `tests/roadmap/refine/test_roadmap_refine_ready_edits.py` at runtime with `NameError`.

## What Changes
Update Ready-item trusted comment detection to use `RefineRecordKey.READ_AT` and `_since_wait_start` rather than removed `_repeated_at`:

- Replace `_repeated_at(item)` in `_has_trusted_comment_since_last_round` (`src/devops_cli/roadmap/refine/refine.py`) by delegating to `_since_wait_start(item, comments)` when a refine marker comment is present, and comparing against `_read_at(item)` when no marker comment exists yet.
- Update `Requirement: New trusted comment is refinable` in `openspec/specs/roadmap-refine/selection/spec.md` to reference `refine.read_at` instead of `refine.repeated_at`.
- Update `tests/roadmap/refine/test_roadmap_refine_ready_edits.py` to seed and test `RefineRecordKey.READ_AT` (`read_at`), including a trusted comment posted between `read_at` and refine's marker comment.

This alters observable selection behavior on Ready items holding `refine.read_at` and updates the existing `roadmap-refine/selection` specification requirement (`MODIFIED`), so it carries a spec delta. Fits in one pull request.

## Capabilities
- `roadmap-refine/selection` (`openspec/specs/roadmap-refine/selection/spec.md`)

## Impact
- `src/devops_cli/roadmap/refine/refine.py`: `_has_trusted_comment_since_last_round`.
- `openspec/specs/roadmap-refine/selection/spec.md`: `Requirement: New trusted comment is refinable`.
- `tests/roadmap/refine/test_roadmap_refine_ready_edits.py`: updated `READ_AT` cases and in-flight comment coverage.

## Feasibility
Confirmed against `origin/main` (`ac8bdebdb`):
- `ruff check`, `mypy`, and `uv check` fail at `src/devops_cli/roadmap/refine/refine.py:3493` (`Name "_repeated_at" is not defined`).
- `src/devops_cli/roadmap/refine/refine.py:2893-2933` already provides `_read_at(item)` and `_since_wait_start(item, comments)`, which implements the `RefineRecordKey.READ_AT` comparison with refine-marker fallback and job-comment exclusion.

## Existing Tool Considered
No external tool covers internal `RefineRecordKey.READ_AT` comment filtering on in-repo roadmap items (`#6371`, `#6452`). Reusing `_read_at` and `_since_wait_start` deletes the stale inline timestamp scan in `_has_trusted_comment_since_last_round` rather than introducing new logic (~1k tokens, <15 min).
