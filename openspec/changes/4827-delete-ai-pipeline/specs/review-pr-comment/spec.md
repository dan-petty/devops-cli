## Purpose

What the pull request comment of a review holds, so that it states only what the review ran.

## ADDED Requirements

### Requirement: A review comment names no persona
The pull request comment of a review SHALL name the files it checked and the analyzers that ran. It SHALL NOT name a persona, in a `Personas:` line or in a `Review by` heading, because no review stage runs a persona. The model notes of each result SHALL follow one another under one `Model Notes (Not Verified)` heading.

#### Scenario: A review with no findings
- **WHEN** a review with no findings formats its comment
- **THEN** the comment names the files and the analyzers, and has no `Personas:` line

#### Scenario: A review with findings
- **WHEN** a review with findings formats its comment
- **THEN** the findings follow the `AI Code Review` heading, and the comment has no `Review by` heading
