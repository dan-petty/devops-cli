# Tasks

## 1. Post event comment on changed deferrals and wrap module docstring

> Kind: behavior

- [x] 1.1 Add failing tests for a second deferred filing posting its event comment without `#<n>` when no comment intervened and for `refine.__doc__` lines being at most 100 characters
  - Verification: `$ uv run pytest -q tests/roadmap/refine/test_roadmap_refine_event_comment.py tests/roadmap/stores/test_roadmap_store_contract.py`
- [x] 1.2 Pass `allow_repeat=tuple(deferred) != recorded_deferred` from `_apply_refined` to `RoadmapStore.comment` (`GitHubRoadmapStore.comment`, `InMemoryRoadmapStore.comment`) and wrap `src/devops_cli/roadmap/refine/refine.py` module docstring lines to at most 100 characters
  - Verification: `$ uv run pytest -q tests/roadmap/refine/ tests/roadmap/stores/test_comment_repeat.py`

Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
