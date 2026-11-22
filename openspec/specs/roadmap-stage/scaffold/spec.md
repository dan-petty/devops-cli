# roadmap-stage/scaffold Specification

## Purpose
How the stage job keeps the App-only branch of a Ready item when it judges the `stage.pending` mark of that item.

## Requirements

### Requirement: The orphan cleanup keeps an App-only branch of a Ready item
The stage job MUST NOT delete an App-only branch of a Ready item when it judges a `stage.pending` mark.

#### Scenario: An orphan mark on a Ready item with an App-only branch
- **WHEN** a Ready item holds a `stage.pending` mark older than 1 hour and its branch holds only App commits
- **THEN** the job makes no delete of the branch
