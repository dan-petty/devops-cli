## ADDED Requirements

### Requirement: A stop site passes a typed class
Each stop of the job whose cause has a class SHALL pass that class, and the stop comment and `implement.failure` SHALL hold it. The classifier SHALL NOT decide a class that a site passes. The words of the last message of the agent and the words of a task SHALL NOT change a class. A step that changed no file SHALL pass `no_change_in_fix` in a fix step and `plan_defect` in a group step.

#### Scenario: A fix step that changed no file
- **WHEN** a fix step stops with the reason "The agent changed no file." and its last message says "The item is already implemented."
- **THEN** the comment holds the class `no_change_in_fix` and `implement.failure` is `no_change_in_fix`

#### Scenario: A group step that changed no file
- **WHEN** the step of group 2 stops with the reason "The agent changed no file."
- **THEN** the class is `plan_defect`

#### Scenario: A task that is not ticked
- **WHEN** the step of group 1 ends with a task unticked whose text holds `devops ci test`
- **THEN** the class is `not_ticked`

#### Scenario: A lost test, a moved HEAD and the output cap
- **WHEN** a step stops because the agent removed a test, moved HEAD, or reached the output cap
- **THEN** the classes are `tests_lost`, `head_moved` and `output_cap`

#### Scenario: The tier decision
- **WHEN** a turn ends with an error whose text the classifier reads as `parser`, and a second turn ends with the output cap and a message that holds the words of a parser failure
- **THEN** the step moves to the next tier after the first turn only, and the outcome of the step holds the class `parser` for the first and `output_cap` for the second, the class that the decision read

### Requirement: A stop names the failed check and the end of its log
A stop of a fix step, and a stop of the scoped checks, SHALL name the failed check and hold the end of its log, at most `CONST_ROADMAP_IMPLEMENT_CHECK_LOG_CHARS` characters, with secrets masked. The stop comment and the job record (`implement.check`, `implement.check_log`) SHALL hold both. A retry or a clear rule of the Service SHALL remove both with the stop. The table of the comment SHALL show the check name as the last failing command when no command failed.

#### Scenario: A fix step that stops
- **WHEN** the check `Tests & Coverage` of the pull request fails with a log that holds a token, and the fix step changes no file
- **THEN** the comment names `Tests & Coverage`, holds the end of the log with the token masked, the row `fix` of the table shows the check name, and `implement.check` and `implement.check_log` hold the same

#### Scenario: A scoped check that still fails
- **WHEN** the scoped check `pre-push` fails after the last fix round
- **THEN** the comment and the record hold the name `pre-push` and the end of its log

#### Scenario: A retry
- **WHEN** a trusted person comments `implement: retry` and the job takes the item
- **THEN** `implement.check` and `implement.check_log` are removed

### Requirement: The comment puts the failed check first and labels the claim
The stop comment SHALL start, after the step, with the failed check. The failed check is the check that the stop names, or else the last command of the step that did not exit 0. The class lines SHALL follow it, and the reason SHALL follow them. The comment SHALL name the last message of the agent as a claim that no check verified.

#### Scenario: The order of the comment
- **WHEN** a stop has a failed check, a reason and a last message
- **THEN** the failed check comes before the class lines, the class lines come before the reason, and the last message follows a label that says that no check verified it

### Requirement: The report reads the item again
`_report` of the Service SHALL read the item again after it reads the log of the Job and before it decides whether the Job left a stop. A stop that the runner wrote in that time SHALL keep its class, and the Service SHALL write no second class.

#### Scenario: The runner stops while the report reads the log
- **WHEN** the item is In Progress in the listing of the round, and the runner writes its stop with the class `timeout` while the report reads the log of the Job
- **THEN** the record keeps the class `timeout`, the report names `timeout`, and the counter for `timeout` grows by 1

### Requirement: The metric labels are classes of the taxonomy
Each panel and alert rule of `k8s/` that reads `devops_cli_service_implement_failures_total` SHALL match the label `class` only with values of the taxonomy.

#### Scenario: A matcher with an unknown value
- **WHEN** a test reads the files of `k8s/` that name the metric
- **THEN** every value of a `class` matcher in them is a class of the taxonomy
