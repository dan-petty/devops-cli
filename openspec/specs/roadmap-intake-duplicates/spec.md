# roadmap-intake-duplicates Specification

## Purpose
What `devops roadmap intake` does with a candidate that the model judges a duplicate of an item: it places the candidate, names the possible original for a person, and never drops a candidate or closes an issue. It also covers the retry of a run that stopped after it filed a new candidate.

## Requirements

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
When an open issue with no `priority/*` label holds the title and the filed body of a new candidate, intake SHALL place that issue, SHALL file no issue, and the entry point SHALL return its number.

#### Scenario: A run stopped after it filed the candidate
- **WHEN** an open issue with no `priority/*` label holds the title and the filed body of a new candidate, and intake runs for that candidate
- **THEN** intake labels that issue `status/new`, the repository holds one issue, and the outcome names that issue

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

### Requirement: An evaluation run takes intake's verdict for each case
`devops roadmap intake-eval` SHALL run each case of the intake duplicate evaluation set through intake with the configured `analysis` model, one case at a time, and SHALL write nothing. For each case it SHALL seed a roadmap that holds the case's item as an item and plan intake for the case's candidate. The verdict SHALL be `duplicate` when the decision names the item as the possible original, `skipped` when intake skips the candidate, and `new item` otherwise.

#### Scenario: A reply that names the item with no shared change
- **WHEN** the model names the case's item as the original of a candidate and gives no shared change
- **THEN** the verdict of that case is `new item`

### Requirement: An evaluation run reports the score of the duplicate verdict
`devops roadmap intake-eval` SHALL print each case with the person's verdict, intake's verdict and whether they agree, then the count of cases that agree, and the precision and the recall of the `duplicate` verdict with the count of false duplicates.

#### Scenario: A model that folds one related item
- **WHEN** the model names the item with a shared change for each case that a person judged a duplicate, and for one case that a person judged a new item, and names no original for the other cases
- **THEN** the command exits 0, the table shows that one case as failed, and the report gives a duplicate precision of 3 of 4, a recall of 3 of 3, and 1 false duplicate

#### Scenario: A model that agrees with every case
- **WHEN** the model names the item with a shared change for each case that a person judged a duplicate, and names no original for the other cases
- **THEN** the command exits 0, every case agrees, and the report gives a duplicate precision of 3 of 3 and no false duplicate

### Requirement: An evaluation run that cannot run a case says so
When a case's model call fails, `devops roadmap intake-eval` SHALL show that case with its error, SHALL go on with the other cases, and SHALL exit 1.

#### Scenario: The model fails for one case
- **WHEN** the model call of one case fails
- **THEN** the table shows that case with its error, the other cases have their verdicts, and the command exits 1

### Requirement: An evaluation run reads the labels of the checkout
`devops roadmap intake-eval` SHALL read the type labels from `.github/labels.yml` at the root of the checkout it runs in, and SHALL send no GitHub request and no embedding request. With no such file it SHALL stop before any model call with an error that names the file.

#### Scenario: A checkout with no labels file
- **WHEN** the command runs in a directory with no `.github/labels.yml`
- **THEN** it exits 1 with an error that names `.github/labels.yml`, and the model gets no call

### Requirement: An evaluation dry run makes no request
`devops roadmap intake-eval --dry-run` SHALL make no request and SHALL list each case with the one `analysis` call that a run makes for it.

#### Scenario: The dry run of the set
- **WHEN** `devops roadmap intake-eval --dry-run` runs
- **THEN** it lists the 16 cases and 16 `analysis` calls, and the model gets no call
