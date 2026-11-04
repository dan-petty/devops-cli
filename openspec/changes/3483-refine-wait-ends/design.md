# Design

## Decision 1: A stage comment on an item with no staged branch is a return

The stage job writes one marked comment when it returns an item, and one when it stages or stops an item. A staged item holds `stage.branch`. A returned item holds none. The rule reads the record and the marker, and no comment text.

- Rejected: a new marker for the return comment. #3478 removes the return path of the stage job, so no new return comment is written, and the old comments carry the stage marker only.
- Rejected: parse the text "returned the item to New". The text is a message that can change.

## Decision 2: One record key counts the returns of a body

`refine.returned_body_hash` holds the body hash of a round that looked again after a return, and apply clears it when a round follows no return. A return finds the key equal to `refine.body_hash` only when this body already had one new look.

- Rejected: count the stage comments in the thread. A body edit between two returns makes the count wrong, and a model would need the same count.
- Rejected: no bound. A round that sets Ready and a stage job that returns the item loop at the speed of the cap of comments.

## Decision 3: The text of the last refine comment is the wait text

The comment that refine wrote for a person wait holds the open questions. The rule reads issue numbers and file paths from it. It reuses the cited-path pattern of refine, and an issue pattern that skips `owner/repo#N`, a number in a path and a number in a word.

- Rejected: record the named issues and files in new job-record keys. It needs a write for each wait and does not cover the waits recorded before the change.
- An issue that closed before the comment is no new cause, so the rule reads the close time. It reads the timeline only for a closed issue whose `updated_at` is not older than the comment.

## Decision 4: Inbox and explain use the record and the real selection

The inbox reads the job record only, as it reads no comment. `explain` calls `refine_left_out`, which runs the selection rules of a round for one item, so the answer cannot differ from a round.
