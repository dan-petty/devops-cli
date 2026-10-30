## Purpose
How `devops ci job-time` finds out whether a CI job, by default the test job, still averages less than five minutes over its last runs on `main`, so that AGENTS.md rule 5 is checked on the history of the runner and not on the one run of a pull request.

## ADDED Requirements

### Requirement: The mean time of the test job over its last runs is checked
The `devops ci job-time` command SHALL read from the GitHub Actions API the time of a named job in the last successful `push` runs of a workflow on a branch. By default it SHALL read the job `Tests & Coverage` of `ci.yml` on `main`, 10 runs, with a limit of 300 seconds. The time of a run SHALL be the time from the start of the job to its end. The command SHALL exit 0 when the mean of the runs is not over the limit, and exit 1 when it is. It SHALL print the time of each run read and the mean.

#### Scenario: The mean is inside the limit
- **WHEN** the last 10 successful runs of the job took 100 seconds each and the user runs `devops ci job-time`
- **THEN** the command exits 0 and the output names the mean of 100 seconds and the limit of 300 seconds

#### Scenario: The mean is over the limit
- **WHEN** the last 10 successful runs of the job took 400 seconds each and the user runs `devops ci job-time`
- **THEN** the command exits 1 and the output names the mean of 400 seconds and says that it is over the limit

#### Scenario: The mean is on the limit
- **WHEN** the mean of the runs is exactly the limit
- **THEN** the command exits 0

#### Scenario: One slow run among fast ones
- **WHEN** 9 of the 10 runs took 250 seconds and one took 400 seconds
- **THEN** the mean is 265 seconds and the command exits 0

#### Scenario: The count and the limit are options
- **WHEN** the user runs the command with `--runs 2 --limit 120` and the last two runs took 100 and 200 seconds
- **THEN** the command exits 1, and with `--limit 150` it exits 0

### Requirement: A short read never passes
The command SHALL exit 1 when GitHub gave fewer runs of the job than the command asked for, and its output SHALL name how many it read and how many it asked for. The mean of fewer runs SHALL NOT pass.

#### Scenario: Three runs of ten
- **WHEN** only 3 successful runs hold the job, each inside the limit, and the user runs `devops ci job-time`
- **THEN** the command exits 1 and the output says that only 3 of the last 10 runs were read

### Requirement: Only a successful job of a successful run counts
The command SHALL list only the runs that GitHub reports as successful `push` runs of the workflow on the branch. A listed run that has no job of the given name, or whose job did not end with the conclusion `success`, SHALL NOT count and SHALL NOT take a place among the wanted runs. The command SHALL follow the next link of the listing, and SHALL stop asking for the jobs of runs once the wanted runs are read.

#### Scenario: A run without the job
- **WHEN** the newest run has no job of that name and the older runs have it
- **THEN** the run is left out and the runs after it are read in its place

#### Scenario: A job that failed
- **WHEN** the job failed in one run
- **THEN** that run is left out

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
The workflow `ci.yml` SHALL hold a job that runs `devops ci job-time` after each push to `main` and on its daily schedule, and no pull request SHALL wait for it. The job SHALL read the history of `main` with a token that can only read the repository contents and the Actions runs.

#### Scenario: A push to main
- **WHEN** a commit is pushed to `main`
- **THEN** the run of `ci.yml` has a job `Test Job Duration` that runs `devops ci job-time`

#### Scenario: A pull request
- **WHEN** a pull request is opened or updated
- **THEN** the run has no job `Test Job Duration`
