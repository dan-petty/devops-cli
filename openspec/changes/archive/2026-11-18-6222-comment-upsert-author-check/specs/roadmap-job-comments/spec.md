# roadmap-job-comments Specification

## MODIFIED Requirements

### Requirement: Shared marked-comment writer
The roadmap SHALL provide one marked-comment writer in `steps/comment.py` with `post(target, marker, key, body)`. It SHALL edit an existing marked comment only when the comment author login equals the GitHub session login.

#### Scenario: Writer updates an existing marked comment
- **WHEN** A target already holds a comment with the marker and key whose author login equals the GitHub session login.
- **THEN** The writer edits that comment and adds no second comment.

#### Scenario: Marked comment of another author is not edited
- **WHEN** A target holds a comment with the marker and key whose author login does not match the GitHub session login.
- **THEN** The writer creates a new comment and does not edit the other author's comment.

#### Scenario: Marked comment with no author login is not edited
- **WHEN** A marked comment has no author login.
- **THEN** The writer creates a new comment and leaves the comment unchanged.
