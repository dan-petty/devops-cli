# Design

## Decisions

- **The check is a pure function `criterion_problems(criteria, issue_body)` that `check_proposal` appends to its other problems.**: It follows `path_problems` (#3010): the reply goes back once through the existing `stage_invalid` path, with no new loop and no new error class.
- **`check_proposal` takes the issue body as a new argument, and `stage.py` passes the body of the item it already holds.**: The criteria come from the issue body, and the job has it in `_request` and in the target item.
- **A criterion matches an entry by its text after trimming the whitespace around it.**: The text comes from the same issue body, so an exact match is deterministic and testable offline.
- **Each entry holds `criterion`, `group` (an integer or `pending-person`) and `reason`.**: The issue states this shape, and a reason is required when a person must deliver the criterion.
- **`tasks.md` gains a Criteria section after the task groups.**: It keeps the group task lists unchanged and makes the mapping easy to scan.
- **The stage prompt states the criteria rule as well as the schema and the check.**: Without the prompt line the model may omit the field and waste a retry.

## Rejected alternatives

- **Fuzzy or semantic matching of criterion text.**: The text comes from the same issue body, so a similarity library or a model call adds cost and a source of drift that an exact match avoids.
- **Match by index, first criterion to first entry.**: The model may reorder or skip entries, and an index cannot tell a skip from a reorder.
- **Annotate each group's task list with its criteria instead of a separate section.**: It clutters the task list and hides which tasks belong to which criterion.
