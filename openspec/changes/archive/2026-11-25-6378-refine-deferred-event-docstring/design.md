# Design

## Decisions

- **Explicit repeat override on changed deferrals (`allow_repeat: bool = False`)**: Compare applied deferred issue numbers against `tuple(_recorded_numbers(r.item))` before writing marks in `_apply_refined` (`src/devops_cli/roadmap/refine/refine.py`). When `tuple(deferred) != recorded_deferred`, pass `allow_repeat=True` to `store.comment` (`RoadmapStore.comment`, `GitHubRoadmapStore.comment`, `InMemoryRoadmapStore.comment`) so `refused_repeat` does not suppress the new deferral event even when its visible text matches the prior comment. Because `store.set_marks` persists the updated `RefineRecordKey.DEFERRED` right before `store.comment`, any subsequent unchanged rerun sees matching deferrals and still suppresses duplicates.
- **Keep comment text unchanged**: Do not embed `#22` or deferred section lines into the event comment text so existing `roadmap-refine/comments` invariants hold.
- **Reflow `refine.py` module docstring**: Wrap every line in `src/devops_cli/roadmap/refine/refine.py`'s module docstring at <= 100 characters while preserving all content.

## Rejected alternatives

- **Include deferred issue numbers in the event comment**: Rejected because `roadmap-refine/comments` forbids section content lines in the event comment.
- **Bypass `refused_repeat` unconditionally for refine comments**: Rejected because duplicate comments on unchanged rounds would flood issues again.
