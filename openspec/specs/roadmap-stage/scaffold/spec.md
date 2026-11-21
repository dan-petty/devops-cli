# roadmap-stage/scaffold Specification

## Purpose
How the stage job keeps the App-only branch of a Ready item when it judges the `stage.pending` mark of that item.

## Requirements

### Requirement: The orphan cleanup keeps an App-only branch of a Ready item
The stage job MUST NOT delete an App-only branch of a Ready item when it judges a `stage.pending` mark. It SHALL keep the mark with the branch, so that a later round resumes on the branch (#6668).

#### Scenario: An orphan mark on a Ready item with an App-only branch
- **WHEN** a Ready item holds a `stage.pending` mark older than 1 hour and its branch holds only App commits
- **THEN** the job makes no delete of the branch, and the item keeps the mark

#### Scenario: The next round after the cleanup of the Service
- **WHEN** a stage Job pushed the branch and died before its draft, and the stage row of the Service then judged the mark
- **THEN** the next stage Job resumes on the kept branch and stages the item with no plan call
