# ci-job-time Specification

## Purpose
How `devops ci job-time` finds out whether a CI job, by default the test job, still averages less than five minutes over its last runs on `main`, so that AGENTS.md rule 5 is checked on the history of the runner and not on the one run of a pull request.

## Requirements

### Requirement: The mean time of the test job over its last runs is checked
The `devops ci job-time` command SHALL read from the GitHub Actions API the time of a named check in the last completed `push` runs of a workflow on a branch. By default it SHALL read the check `Tests & Coverage` of `ci.yml` on `main`, 20 runs, with a limit of 300 seconds. The command SHALL exit 0 when the mean of the runs is not over the limit, and exit 1 when it is. It SHALL print the time of each run read and the mean.

#### Scenario: The mean is inside the limit
- **WHEN** the last 20 runs of the job took 100 seconds each and the user runs `devops ci job-time`
- **THEN** the command exits 0 and the output names the mean of 100 seconds and the limit of 300 seconds

#### Scenario: The mean is over the limit
- **WHEN** the last 20 runs of the job took 400 seconds each and the user runs `devops ci job-time`
- **THEN** the command exits 1 and the output names the mean of 400 seconds and says that it is over the limit

#### Scenario: The mean is on the limit
- **WHEN** the mean of the runs is exactly the limit
- **THEN** the command exits 0

#### Scenario: One slow run among fast ones
- **WHEN** 19 of the 20 runs took 250 seconds and one took 400 seconds
- **THEN** the mean is 257.5 seconds and the command exits 0

#### Scenario: The count and the limit are options
- **WHEN** the user runs the command with `--runs 2 --limit 120` and the last two runs took 100 and 200 seconds
- **THEN** the command exits 1, and with `--limit 150` it exits 0

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

### Requirement: A short read never passes
The command SHALL exit 1 when GitHub gave fewer runs of the job than the command asked for, and its output SHALL name how many it read and how many it asked for. The mean of fewer runs SHALL NOT pass.

#### Scenario: Three runs of twenty
- **WHEN** only 3 runs hold the job, each inside the limit, and the user runs `devops ci job-time`
- **THEN** the command exits 1 and the output says that only 3 of the last 20 runs were read

### Requirement: The conclusion of the job counts, not the conclusion of the run
The command SHALL list the completed `push` runs of the workflow on the branch, whatever their conclusion. A run SHALL count when its job of the given name ended with `success`, `failure` or `timed_out`, and has a start and an end. Any other run SHALL NOT count and SHALL NOT take a place among the wanted runs. A run that failed for another job still holds the time of the test job, and a slow run that failed is the run the check must see.

#### Scenario: A run without the job
- **WHEN** the newest run has no job of that name and the older runs have it
- **THEN** the run is left out and the runs after it are read in its place

#### Scenario: A job that was cancelled
- **WHEN** the job was cancelled in one run
- **THEN** that run is left out

#### Scenario: A job that failed or timed out
- **WHEN** the job failed or timed out in one run, and the run concluded with a failure
- **THEN** the time of the job counts as one of the wanted runs

#### Scenario: A slow failed run among fast ones
- **WHEN** 19 of the 20 runs took 250 seconds and one failed run took 600 seconds
- **THEN** the mean is 267.5 seconds and the command exits 1 for a limit of 260 seconds

### Requirement: Only the wanted runs are read
The command SHALL follow the next link of the listing of runs, and SHALL stop asking for the jobs of runs once the wanted runs are read.

#### Scenario: A second page of runs
- **WHEN** the listing links a next page
- **THEN** the runs of the next page count when the first page holds fewer than the wanted runs

#### Scenario: No more requests than needed
- **WHEN** the listing holds 12 runs and 10 are wanted
- **THEN** the command asks for the jobs of the first 10 runs only

### Requirement: A dry run makes no request
With `--dry-run` the command SHALL make no request to GitHub. It SHALL list the listing of runs and the request for the jobs of each run, as `devops` dry runs list their requests.

#### Scenario: Dry run
- **WHEN** the user runs `devops ci job-time --dry-run`
- **THEN** the command exits 0, GitHub receives no request, and the output names the listing of the runs of `ci.yml`

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
