# Design

## Decisions

- **Store protocol defines `add_sub_issue(parent: int, child: int) -> None`**: Both arguments are issue numbers. In `GitHubRoadmapStore`, the child's REST ID is retrieved from the stored payload or fetched if not present.
- **Link sub-issue immediately after filing**: Linking happens in `_apply_placement` right after `_placement_target` files the new issue.
- **Support both full issue URLs and issue numbers in `--source`**: Extract the issue number whether `--source` is a URL to the same repository or an issue number. External URLs return None and do not link.
- **Include sub-issue write in dry-run plan**: In `intake_requests.py`, when a new candidate specifies a `--source` that names an issue in the repository, add the sub-issue write to `planned_requests`.

## Rejected Alternatives

- **Pass child REST ID in `RoadmapStore.add_sub_issue`**: Rejected because `MemoryRoadmapStore` and the CLI operate on issue numbers. The store handles REST ID translation internally.
- **Link sub-issues in a separate CLI command**: Rejected because intake already knows the parent from `--source` when filing. Manual linking is error-prone.
