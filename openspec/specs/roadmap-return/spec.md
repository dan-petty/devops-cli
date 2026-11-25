# roadmap-return Specification

## Purpose

Returning an unbuildable leaf roadmap item to New with evidence while rejecting trackers (`type/epic` or sub-issues) with actionable open sub-issue and related-issue guidance.

## Requirements

### Requirement: Return refuses trackers and names actionable sub-issues and related issues
`plan_return` and `devops roadmap return` SHALL refuse any item for which `item.is_tracker` is true (`sub_issues > 0` or label `type/epic`) with `DevOpsCLIError` without writing comments or changing labels. When open sub-issues or open related `#<number>` references in person-written body text exist, the error message SHALL name them; otherwise it SHALL advise closing the delivered tracker or filing sub-issues. Non-tracker items SHALL remain returnable with the same reads and writes.

#### Scenario: Return refuses a tracker with open sub-issues and related links
- **WHEN** `plan_return` or `devops roadmap return` is invoked on a tracker that has open sub-issue `#12` and open related issue `#15` referenced in its body
- **THEN** the call fails with exit code 1 (`DevOpsCLIError`), writes no comment or label change, and names `#12` and `#15` in the error message

#### Scenario: Return refuses an epic tracker with no open sub-issues
- **WHEN** `plan_return` or `devops roadmap return` is invoked on a `type/epic` item that has zero open sub-issues and no open related issues
- **THEN** the call fails with `DevOpsCLIError`, writes nothing, and tells the caller to close the tracker if delivered or file sub-issues instead
