## ADDED Requirements

### Requirement: The record of a run holds how the run ended

The record of a run of a review tool SHALL hold the exit code of the run and whether the run succeeded, as the code that ran the tool decides it. The record SHALL hold no exit code for a run that timed out or that a signal ended.

#### Scenario: A scanner that found something

- **WHEN** Gitleaks ends with exit code 1 and a report that holds a finding
- **THEN** the record of the run holds exit code 1 and success true

#### Scenario: A scanner that timed out

- **WHEN** the run of Gitleaks times out
- **THEN** the record of the run holds no exit code and success false

### Requirement: The outcome of a scan decides the success of its run

A scan SHALL settle its run as succeeded when its outcome is `ran` or `coverage_gap`, and as failed for every other outcome of a run that started. mypy SHALL settle its run as succeeded when it ended with exit code 0 or 1.

#### Scenario: A scanner that failed

- **WHEN** Gitleaks ends with exit code 2 and output that is not JSON
- **THEN** the record of the run holds exit code 2 and success false

#### Scenario: A mypy run that did not finish its check

- **WHEN** mypy ends with exit code 2
- **THEN** the record of the run holds exit code 2 and success false

### Requirement: The recorder keeps the settled record in the place of the run

`RecordingToolExecutor` SHALL keep the settled record of a run in the place of the record of the run, so the records stay in the order the runs started. It SHALL refuse a result that it did not start or that is already settled.

#### Scenario: A result settled two times

- **WHEN** the code that ran a tool settles the same result a second time
- **THEN** `RecordingToolExecutor` raises `ValueError`, and the first settled record stays

### Requirement: The Tool Runs table shows how each record ended

The Tool Runs table of `review.md` SHALL show the exit code and the success of each distinct record, so that two records that differ only in them read as two rows.

#### Scenario: Two runs that ended in different ways

- **WHEN** Gitleaks ran twice with one config, and one run succeeded and one failed
- **THEN** the table shows two rows for Gitleaks, one with `yes` and one with `no` in the column `Succeeded`
