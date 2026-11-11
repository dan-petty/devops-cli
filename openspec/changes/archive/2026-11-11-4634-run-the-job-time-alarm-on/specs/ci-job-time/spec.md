## MODIFIED Requirements

### Requirement: The time of a run covers the shard jobs of the check
The time of a run SHALL be the run time of the job of that name plus the longest run time of its shard jobs, whose names start with that name, a space and an opening parenthesis. The run time of a job SHALL be the time from its start on a runner to its end. The rest of the span from the first start to the end of the job SHALL be the queue time of the run. The command SHALL print the queue time on its own line and SHALL NOT count it against the limit.

#### Scenario: A run with shard jobs
- **WHEN** a run holds the shard jobs `Tests & Coverage (shard 1 of 3)` to `(shard 3 of 3)` that started at 0 s, 3 s and 5 s and ended at 180 s, and the job `Tests & Coverage` that started at 190 s and ended at 250 s
- **THEN** the time of the run is 240 seconds and its queue time is 10 seconds

#### Scenario: A run that waited for runners
- **WHEN** the slowest shard job of a run ran for 427 seconds, the job `Tests & Coverage` ran for 45 seconds, and the span from the first start of a shard to the end of the job is 975 seconds
- **THEN** the time of the run is 472 seconds and its queue time is 503 seconds

#### Scenario: The limit does not count the queue time
- **WHEN** the one run read ran for 472 seconds and waited 503 seconds, and the user runs the command with `--runs 1 --limit 480`
- **THEN** the command exits 0 and prints the queue time of 503 seconds on its own line, and with `--limit 460` it exits 1

#### Scenario: A run with a job of a longer name
- **WHEN** a run holds a job named `Tests & Coverage Report` that started before the job `Tests & Coverage`
- **THEN** the job `Tests & Coverage Report` does not change the time of the run

### Requirement: The workflow runs the check on main
The workflow `ci.yml` SHALL hold a job that runs `devops ci job-time` on its daily schedule and on a manual run, and on no other event. No job SHALL wait for it. The job SHALL read the history of `main` with a token that can only read the repository contents and the Actions runs. The concurrency group of `ci.yml` SHALL hold the event name, so that a push to `main` does not cancel the schedule run.

#### Scenario: The daily schedule
- **WHEN** the schedule starts `ci.yml`
- **THEN** the run has a job `Test Job Duration` that runs `devops ci job-time`

#### Scenario: A push to main
- **WHEN** a commit is pushed to `main`
- **THEN** the run has no job `Test Job Duration`, so the run is green when its other jobs pass

#### Scenario: A pull request
- **WHEN** a pull request is opened or updated
- **THEN** the run has no job `Test Job Duration`

#### Scenario: A push during the schedule run
- **WHEN** a commit is pushed to `main` while the schedule run of `ci.yml` runs
- **THEN** the push run is in another concurrency group, and the schedule run is not cancelled
