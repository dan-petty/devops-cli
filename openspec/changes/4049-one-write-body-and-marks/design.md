# Design

## Decisions

- **`body` is an optional keyword of `set_field` and `set_marks`, and `_edit_issue` takes the text as its own argument.**: The `PATCH` of an issue already carries the labels and the body with the record block, and `set_field` already sends them together. A new text replaces only the part before the record block, so the held block and its marks stay, and the new marks join it.
- **The Status, the marks and the body of one refine result go in one `set_field`.**: A stop between two requests would leave `refine.next_step=ready` on a New item. In `_still_waiting`, `NextStep.READY` on a New item means that the stage job or a person returned it, so the item would get a new look with model spend, and `RETURNED_BODY_HASH` would then make the second pass wait on a person. One request leaves no such state.
- **A Status that stays uses `set_marks(..., body=...)`.**: No label changes, so the request holds the body with the record block only.
- **`write_issue_body` stays.**: `repair.py` writes a body with no marks, and the plan of repair lists it.
- **The comment stays a separate request after the write.**: A stop before the comment loses a comment and not the state. The state is complete after the one write.
- **The race guards stay where they are.**: `_outside_unchanged_since_read` (refine) and `_unchanged_since_read` (alternatives) read the body before the write, and `set_field` reads the issue and calls `require_unchanged`. The write that carries a body still reads the issue once, as every write of a field does.
- **The dry-run plan lists the read of the issue and one `PATCH` for the body, the labels and the record, and no second read and `PATCH`.**: The planned `set_field` and `set_marks` requests already hold the body as the `record` placeholder, so the plan drops the planned `write_issue_body` of the three plans that are no longer real.
- **The in-memory store logs a `write_issue_body` entry in `job_writes` for a combined write.**: Tests that ask which issues a job wrote a body for keep their question, and the order of the entries shows the body before the field and the marks.

## Rejected alternatives

- **Write the body and the marks in one request, and the Status in a second.**: A stop between them leaves `refine.next_step=ready` and a new `refine.body_hash` on a New item. The next round treats it as a return by the stage job, looks at the item again with model spend, and then waits on a person. That moves the window and does not close it.
- **Write the Status first, then the body and the marks.**: A stop after the Status leaves a Ready item with the old design. Nothing in the record tells the next round that the design is old.
- **A new store method that takes the body, the Status and the marks.**: `set_field` already takes the Status and the marks in one write, and `set_marks` takes the marks. One more keyword on each is smaller than a third write path that every store must carry.
- **Keep `write_issue_body` and make the order safe with a marker in the record.**: A marker is a second state for the next round to read and to repair. One request has one state.
