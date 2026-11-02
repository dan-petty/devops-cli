## ADDED Requirements

### Requirement: The intake evaluation runs in the eval group
The CLI SHALL run the intake duplicate evaluation as `devops roadmap eval intake`, and MUST NOT register `devops roadmap intake-eval` as a command or as an alias.

#### Scenario: The eval group holds intake
- **WHEN** A user runs `devops roadmap eval intake --help`.
- **THEN** The command exits 0 and its help text names the intake duplicate evaluation.

#### Scenario: The old command is gone
- **WHEN** A user runs `devops roadmap intake-eval`.
- **THEN** The command exits 2 and reports no such command.

#### Scenario: The eval group lists intake
- **WHEN** A test lists the command names of `eval_app`.
- **THEN** The names include `intake` and hold no `intake-eval`.

### Requirement: The moved evaluation keeps its options and its output
`devops roadmap eval intake` SHALL keep the `--dry-run` option, the scoring output and the exit codes of the evaluation it runs.

#### Scenario: A dry run prints the plan
- **WHEN** A user runs `devops roadmap eval intake --dry-run`.
- **THEN** The command prints the dry-run plan, makes no model call and exits 0.

#### Scenario: A scored run reports each case
- **WHEN** The evaluation runs over the committed cases.
- **THEN** It prints the score of each case with the precision and the recall of the duplicate verdict, and exits 0 when every case ran.

## MODIFIED Requirements

### Requirement: An evaluation run takes intake's verdict for each case
`devops roadmap eval intake` SHALL run each case of the intake duplicate evaluation set through intake with the configured `analysis` model, one case at a time, and SHALL write nothing. For each case it SHALL seed a roadmap that holds the case's item as an item and plan intake for the case's candidate. The verdict SHALL be `duplicate` when the decision names the item as the possible original, `skipped` when intake skips the candidate, and `new item` otherwise.

#### Scenario: A reply that names the item with no shared change
- **WHEN** the model names the case's item as the original of a candidate and gives no shared change
- **THEN** the verdict of that case is `new item`

### Requirement: An evaluation run reports the score of the duplicate verdict
`devops roadmap eval intake` SHALL print each case with the person's verdict, intake's verdict and whether they agree, then the count of cases that agree, and the precision and the recall of the `duplicate` verdict with the count of false duplicates.

#### Scenario: A model that folds one related item
- **WHEN** the model names the item with a shared change for each case that a person judged a duplicate, and for one case that a person judged a new item, and names no original for the other cases
- **THEN** the command exits 0, the table shows that one case as failed, and the report gives a duplicate precision of 3 of 4, a recall of 3 of 3, and 1 false duplicate

#### Scenario: A model that agrees with every case
- **WHEN** the model names the item with a shared change for each case that a person judged a duplicate, and names no original for the other cases
- **THEN** the command exits 0, every case agrees, and the report gives a duplicate precision of 3 of 3 and no false duplicate

### Requirement: An evaluation run that cannot run a case says so
When a case's model call fails, `devops roadmap eval intake` SHALL show that case with its error, SHALL go on with the other cases, and SHALL exit 1.

#### Scenario: The model fails for one case
- **WHEN** the model call of one case fails
- **THEN** the table shows that case with its error, the other cases have their verdicts, and the command exits 1

### Requirement: An evaluation run reads the labels of the checkout
`devops roadmap eval intake` SHALL read the type labels from `.github/labels.yml` at the root of the checkout it runs in, and SHALL send no GitHub request and no embedding request. With no such file it SHALL stop before any model call with an error that names the file.

#### Scenario: A checkout with no labels file
- **WHEN** the command runs in a directory with no `.github/labels.yml`
- **THEN** it exits 1 with an error that names `.github/labels.yml`, and the model gets no call

### Requirement: An evaluation dry run makes no request
`devops roadmap eval intake --dry-run` SHALL make no request and SHALL list each case with the one `analysis` call that a run makes for it.

#### Scenario: The dry run of the set
- **WHEN** `devops roadmap eval intake --dry-run` runs
- **THEN** it lists the 16 cases and 16 `analysis` calls, and the model gets no call
