# Proposal: #6378

## Why

After `#6353` merged onto `main`, two defects remain in `src/devops_cli/roadmap/refine/refine.py`:
1. When a later refine round files another deferred issue (for example `#22` after recorded `RefineRecordKey.DEFERRED` `#21`) without an intervening comment, its event comment text equals the previous event comment text, so `store.comment` refuses it as a repeat and posts no event.
2. Multiple lines in `refine.py`'s module docstring exceed 100 characters.

## What Changes

- Key refine's repeat-guard bypass on whether the applied deferred issue numbers differ from recorded `RefineRecordKey.DEFERRED`, allowing `store.comment` (`RoadmapStore.comment`, `GitHubRoadmapStore.comment`, `InMemoryRoadmapStore.comment`) to post the unchanged-text event comment once when deferrals changed while keeping deferred issue numbers out of the comment text.
- Wrap all lines in `src/devops_cli/roadmap/refine/refine.py`'s module docstring to at most 100 characters without altering documented behavior.
- Add unit tests for both behaviors in `tests/roadmap/refine/test_roadmap_refine_deferred.py` and `tests/roadmap/refine/test_roadmap_refine_event_comment.py`.

## Capabilities

### Modified Capabilities

- `roadmap-refine/comments`: Post the refine event comment when the round's deferred issues differ from recorded `RefineRecordKey.DEFERRED`, and keep `refine.py`'s module docstring lines within 100 characters.

## Impact

- Subsequent refine rounds that file additional deferred parts reliably emit their event comment even with no reply in between.
- Keeps comment text free of section content and deferred issue numbers.

## Feasibility

Verified directly against `origin/main` (`43d458c2f`):
- `src/devops_cli/roadmap/refine/refine.py:4830-4853` calls `store.comment(r.item.number, comment)` after `_file_deferrals`, and `store.comment` calls `refused_repeat` unconditionally.
- `src/devops_cli/roadmap/refine/refine.py:1-75` has multiple lines longer than 100 characters.

## Existing Tool Considered

No open tool or external library governs this repository's internal `RefineRecordKey.DEFERRED` repeat-comment decision or `refine.py` docstring line wrapping; extending `store.comment` with an optional keyword parameter and wrapping the docstring costs under 5k tokens and 30 minutes.
