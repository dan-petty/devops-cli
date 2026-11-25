## MODIFIED Requirements

### Requirement: The orphan cleanup keeps an App-only branch of a Ready item
The stage job MUST NOT delete an App-only branch of a Ready item when it judges a `stage.pending` mark, and SHALL keep `stage.pending` set while clearing the other keys in `STAGE_REMOVAL_KEYS`. The cleanup SHALL clear `stage.pending` when it deletes the branch or clears a gone orphan.

#### Scenario: An orphan mark on a Ready item with an App-only branch
- **WHEN** a Ready item holds a `stage.pending` mark older than 1 hour and its branch holds only App commits
- **THEN** the job makes no delete of the branch, keeps `stage.pending`, and sets the other keys of `STAGE_REMOVAL_KEYS` to `None`

## ADDED Requirements

### Requirement: Budget stop clears the kept mark
A stage round that stops a Ready item on the token budget through `_stop_on_budget` MUST set `stage.pending` to `None` alongside the budget stop record.

#### Scenario: Stop keeps its owner question
- **WHEN** a Ready item resumes on its kept branch and stops on the token budget through `_stop_on_budget`
- **THEN** the record holds `stage.needs_split` and `stage.file_cap`, sets `stage.pending` to `None`, and the next round finds no orphan

### Requirement: Kept branch resumes in the next round
The next stage round SHALL resume on the kept App-only branch of a Ready item and stage the item without leaving it out as held by a pushed branch.

#### Scenario: Next round resumes on kept orphan
- **WHEN** orphan cleanup keeps the App-only branch and `stage.pending` mark of a Ready item and the next round runs `plan_stage`
- **THEN** the next round resumes on the kept branch and stages the item
