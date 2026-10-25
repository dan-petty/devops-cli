## Purpose

What `devops roadmap intake` does with a candidate that the model judges a duplicate of an item: it places the candidate, names the possible original for a person, and never drops a candidate or closes an issue. It also covers the retry of a run that stopped after it filed a new candidate.

## ADDED Requirements

### Requirement: A duplicate verdict places the candidate
When the model names a shortlist item as the original and names the change that both ask for, intake SHALL place the candidate as it places any candidate, and SHALL file a new candidate.

#### Scenario: A new candidate that the model judges a duplicate
- **WHEN** an agent files a new candidate, and the model names a finished item as its original with a shared change
- **THEN** intake files the candidate, places it on the board with Status New, and the report and the reason comment name the item as the possible original

#### Scenario: An existing issue that the model judges a duplicate
- **WHEN** an open issue off the board is a candidate, and the model names an item as its original with a shared change
- **THEN** intake places the issue, the issue stays open, and its reason comment names the possible original

#### Scenario: A person planned the candidate
- **WHEN** the candidate has a milestone or a Priority that a person set, and the model names an original
- **THEN** intake places the candidate like any other, and it stays open

### Requirement: The report and the reason comment name the possible original
For a candidate that the model judges a duplicate, the report SHALL give the line `  - possible duplicate: #<n>. The model names <change> as the change that both ask for. <reason>`. The reason comment SHALL give the line `- Possible duplicate: #<n>, which may ask for the same change.`, then the same reason, then `A person closes one of the two if that is so.`

#### Scenario: A true duplicate of the evaluation set
- **WHEN** the model gives the answer of a case that a person closed as a duplicate
- **THEN** the report line and the comment line name the item and the change of that answer, and the candidate stays open

### Requirement: Intake closes no issue
Intake SHALL make no close request. `devops roadmap intake --dry-run` SHALL list no close request.

#### Scenario: The plan of a possible duplicate
- **WHEN** `devops roadmap intake --plan` decides a candidate that the model judges a duplicate
- **THEN** the report names the possible original and the writes that place the candidate, and names no close

### Requirement: A retry places the issue that a stopped run filed
When an open issue that is not finished, off the board or on it with no Priority, holds the title and the filed body of a new candidate, intake SHALL place that issue, SHALL file no issue, and the entry point SHALL return its number.

#### Scenario: A run stopped after it filed the candidate
- **WHEN** an open issue off the board holds the title and the filed body of a new candidate, and intake runs for that candidate
- **THEN** intake places that issue with Status New, the repository holds one issue, and the outcome names that issue
