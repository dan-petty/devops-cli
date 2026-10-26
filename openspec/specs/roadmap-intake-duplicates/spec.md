# roadmap-intake-duplicates Specification

## Purpose
What `devops roadmap intake` does with a candidate that the model judges a duplicate of an item: it places the candidate, names the possible original for a person, and never drops a candidate or closes an issue. It also covers the retry of a run that stopped after it filed a new candidate.

## Requirements

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

### Requirement: A part is not compared with the other sub-issues of its source
When the source of a new candidate links an issue of the repository, intake SHALL leave that issue and every sub-issue of it out of the items it compares with the candidate. A candidate with no such source SHALL be compared with all items as before.

#### Scenario: A sibling part with a near-identical title
- **WHEN** the source of a new candidate links an issue, and a sub-issue of that issue has a title that is near-identical to the title of the candidate
- **THEN** the items sent to the model for the candidate hold no sub-issue of the source, and the candidate names no possible duplicate

#### Scenario: A sub-issue of another issue
- **WHEN** an item with a near-identical title is a sub-issue of an issue that is not the source of the candidate
- **THEN** the items sent to the model hold that item

#### Scenario: A candidate with no source
- **WHEN** a new candidate has no source, and an item with a near-identical title is a sub-issue of some issue
- **THEN** the items sent to the model hold that item

#### Scenario: A sub-issue whose parent is in another repository
- **WHEN** an item is a sub-issue of an issue that has the number of the source issue but is in another repository
- **THEN** the items sent to the model hold that item
