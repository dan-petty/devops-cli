## MODIFIED Requirements

### Requirement: A duplicate verdict places the candidate
When the model names a shortlist item as the original and names the change that both ask for, intake SHALL place the candidate as it places any candidate, and SHALL file a new candidate.

#### Scenario: A new candidate that the model judges a duplicate
- **WHEN** an agent files a new candidate, and the model names a finished item as its original with a shared change
- **THEN** intake files the candidate, labels it `status/new` and with its Priority, and the report and the reason comment name the item as the possible original

#### Scenario: An existing issue that the model judges a duplicate
- **WHEN** an open issue with no `priority/*` label is a candidate, and the model names an item as its original with a shared change
- **THEN** intake places the issue, the issue stays open, and its reason comment names the possible original

#### Scenario: A person planned the candidate
- **WHEN** the candidate has a milestone or a Status that a person set, and the model names an original
- **THEN** intake places the candidate like any other, and it stays open

### Requirement: A retry places the issue that a stopped run filed
When an open issue with no `priority/*` label holds the title and the filed body of a new candidate, intake SHALL place that issue, SHALL file no issue, and the entry point SHALL return its number.

#### Scenario: A run stopped after it filed the candidate
- **WHEN** an open issue with no `priority/*` label holds the title and the filed body of a new candidate, and intake runs for that candidate
- **THEN** intake labels that issue `status/new`, the repository holds one issue, and the outcome names that issue
