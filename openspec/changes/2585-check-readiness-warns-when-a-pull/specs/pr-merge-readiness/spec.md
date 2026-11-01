## ADDED Requirements

### Requirement: body-length-advisory-threshold
The readiness verdict SHALL add no advisory when the body, with trailer lines removed, is at most 1,000 characters.

#### Scenario: body at the limit
- **WHEN** The body before trailers is exactly 1,000 characters
- **THEN** No advisory is present in the verdict

### Requirement: body-length-advisory-trigger
The readiness verdict SHALL add one WARNING advisory when the body, with trailer lines removed, is longer than 1,000 characters.

#### Scenario: body over the limit
- **WHEN** The body before trailers is 1,001 characters
- **THEN** One WARNING advisory names 1,001, 1,000, and CONTRIBUTING.md section 4

### Requirement: trailer-exclusion
Trailer lines (Closes, Change:, Fail-to-pass:, Co-authored-by:, Signed-off-by:) SHALL NOT count toward the body length.

#### Scenario: trailer lines stripped
- **WHEN** The body contains trailer lines and the remaining text is 1,000 characters
- **THEN** No advisory is present in the verdict

### Requirement: advisory-does-not-block
A body-length WARNING advisory SHALL NOT change the exit code of devops pr check-readiness.

#### Scenario: exit code unchanged
- **WHEN** The verdict contains a body-length WARNING advisory and no blockers
- **THEN** The exit code is the same as when no advisory is present
