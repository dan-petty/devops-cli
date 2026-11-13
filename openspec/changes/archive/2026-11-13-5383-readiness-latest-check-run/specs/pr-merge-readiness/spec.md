## ADDED Requirements

### Requirement: Only the latest run of each check counts
The reader of the check runs of a commit SHALL keep only the latest run of each check, whatever the conclusion of that run. A check SHALL be the name of the run and the id of the app that reports it. The time of a run SHALL be its `started_at`, else its `completed_at`. A run with no time, and each run at the latest time of its check, SHALL stay. `devops pr ready`, `devops pr check-readiness` and the roadmap readiness rows SHALL judge the checks through this reader.

#### Scenario: A newer run passes after an older run failed
- **WHEN** the head commit has a failed run of Fail-to-Pass Check and a newer passed run of it in another check suite, and the latest run of each other check passed or was skipped
- **THEN** `devops pr ready` marks the pull request ready and exits 0, and `devops pr check-readiness` exits 0

#### Scenario: A newer run fails after an older run passed
- **WHEN** the head commit has a passed run of Fail-to-Pass Check and a newer failed run of it
- **THEN** `devops pr ready` and `devops pr check-readiness` both exit 1 and name Fail-to-Pass Check

#### Scenario: A newer run still runs
- **WHEN** a check has a passed run and a newer run that still runs
- **THEN** the check is pending

#### Scenario: Two apps report a check of one name
- **WHEN** one app reports a failed run of a check, and another app reports a newer passed run of a check with the same name
- **THEN** both runs stay, and the checks do not pass
