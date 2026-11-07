# Design

## Decisions

### The mark is the count of comments

`refine.comments_seen` holds `Item.comments`, the count that the issue listing carried when a round read the comments. The listing is read in each round already. A later round compares the count with the record. The match means that no comment was added since the read, so the replies, the time of refine's last comment and the wait text are those of the record.

- Rejected: the `updated_at` of the item, as issue #3667 proposed. Every write moves it, also the write of the record, so the mark never matches (see Feasibility in the proposal).
- Rejected: one read of the comments of the repository since a time (`comments_since`). It reads each comment of every item since the oldest wait, and the oldest wait is old.
- Rejected: a conditional GET of the comment list (ADR 0006).

### The record is written by the round that reads

The selection is a plan and writes nothing. A waiting item carries `marks`, as it carries `cap_stop`, and apply records them. The round that follows a refine comment reads the comments once, because the new comment moved the count. The record then holds the new count, and the round after it reads none. A comment that is no reply, such as a comment of the alternatives job, moves the count in the same way.

- Rejected: write the marks when refine posts its comment. The count after the comment is not known to the round, because a person can comment while the model works. A count that is too low only costs one read. Yet this adds a second place that builds the marks, and the round that reads does it with one.

### The other exits use the record

`refine.commented_at` replaces the time of the last comment that `_cited_code_changed` and `_named_cause_ended` read from the comments. `refine.wait_refs` holds the issues and paths that the wait text names, the first `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` of each, so the bound of the reads stays. A closed blocker needs no comment.

### What still reads

An item that refine set Ready and was set back to New needs the comments to find a stage return, and an item of an account that the jobs do not trust needs them to find the notice. Both are few and keep their read. The docstring says so.
