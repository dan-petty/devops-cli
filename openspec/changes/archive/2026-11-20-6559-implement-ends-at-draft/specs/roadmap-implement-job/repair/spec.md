## MODIFIED Requirements

### Requirement: A stop names the failed check and the end of its log
A stop of a fix step, and a stop of the scoped checks, SHALL name the failed check and hold the end of its log, at most `CONST_ROADMAP_IMPLEMENT_CHECK_LOG_CHARS` characters, with secrets masked. The stop comment and the job record (`implement.check`, `implement.check_log`) SHALL hold both. The next Job SHALL remove `implement.check_log` in its first record write. The comment table SHALL show the check name as the last failing command when no command failed.

#### Scenario: A fix step that stops
- **WHEN** the scoped check `pre-push` fails with a log that holds a token, and the fix step changes no file
- **THEN** the comment names `pre-push`, holds the end of the log with the token masked, the row `fix` of the table shows the check name, and `implement.check` and `implement.check_log` hold the same

#### Scenario: A scoped check that still fails
- **WHEN** the scoped check `pre-push` fails after the last fix round
- **THEN** the comment and the record hold the name `pre-push` and the end of its log

#### Scenario: A retry
- **WHEN** a trusted person comments `implement: retry` and the job takes the item
- **THEN** `implement.check` and `implement.check_log` are removed

#### Scenario: A clear rule keeps the log
- **WHEN** a clear rule of the Service removes the stop of an item
- **THEN** `implement.check` is removed and `implement.check_log` stays

## REMOVED Requirements

### Requirement: A failed check of the pull request gets bounded fix steps
**Reason**: The implement Job ends at the draft pull request and watches no check (#6559).
**Migration**: The watch row runs the ready path of the step `fix-checks` on the draft, and the watch row starts a fix-checks Job for a failed check of the classes `test`, `lint`, `types` and `plan_defect` (specs `roadmap-watch-row` and `roadmap-fix-checks`).

### Requirement: A failed check outside the repair scope gets no fix turn
**Reason**: The implement Job ends at the draft pull request and watches no check (#6559).
**Migration**: The step `fix-checks` judges the scope of a failed check with `fix_checks_cause` before its model fix.
