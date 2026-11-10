## ADDED Requirements

### Requirement: The screen eval scores the cascade on two fixed halves
`devops roadmap eval screen` SHALL ask Jev the questions of the screen about each case of the golden set, read stored runs of the reviewer alone, fit the cuts on one half of `split.json` and score them on the other, and repeat with the halves swapped. It SHALL print, for each fit, the skipped reviews, the serious defects of the reviewer that the cascade loses, the false clears, the oracle and the cost of a plan with and without the screen. It SHALL call no reviewer.

#### Scenario: A cleared case with a serious defect
- **WHEN** the reviewer alone found a serious defect in a case and the cuts clear that case
- **THEN** the report counts the defect as lost and says that the bar is not met

#### Scenario: The oracle
- **WHEN** the reviewer alone found no serious defect in some cases
- **THEN** the report gives their number as the most reviews that any screen can skip with no loss

### Requirement: The screen eval makes no request when asked not to
With `--dry-run`, and with `--from` an earlier report, `devops roadmap eval screen` SHALL make no request to Jev.

#### Scenario: Dry run
- **WHEN** `devops roadmap eval screen --dry-run` runs
- **THEN** the output names one request for each case and no request is made
