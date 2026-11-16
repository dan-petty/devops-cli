# roadmap-job-comments Specification

## ADDED Requirements

### Requirement: Shared marked-comment writer
The roadmap SHALL provide one marked-comment writer in `steps/comment.py` with `post(target, marker, key, body)`.

#### Scenario: Writer updates an existing marked comment
- **WHEN** A target already holds a comment with the marker and key.
- **THEN** The writer edits that comment and adds no second comment.

### Requirement: Marker read before post
The writer SHALL read the target's marked comments before it writes a comment.

#### Scenario: Read precedes write
- **WHEN** The writer posts a marked comment to a target.
- **THEN** The target records a comment list before the create or update call.

### Requirement: Repeat guard refuses a repeat
The writer MUST rely on the #4793 store guard to refuse a repeated marked comment.

#### Scenario: Second run posts nothing
- **WHEN** The same marker, key and body already exist on the target.
- **THEN** The writer makes no comment write, and the store guard refuses the repeat.

### Requirement: All comment sites use one writer
Every roadmap module that posts a marked comment SHALL call `steps/comment.py`, and no other module SHALL call `comment_on_issue` or `comment_on_pull`.

#### Scenario: Structural test rejects a direct caller
- **WHEN** A module outside `steps/comment.py` calls `comment_on_issue` or `comment_on_pull`.
- **THEN** The structural test fails.

### Requirement: Stop replay leaves no extra comments
The stage, refine and implement jobs SHALL pass the stop-after-each-write harness with no extra comments.

#### Scenario: A stop after each write leaves no extra comment
- **WHEN** `stop_after_each_write` runs each job.
- **THEN** `StopReplay.extra_comments()` is empty for every stop.
