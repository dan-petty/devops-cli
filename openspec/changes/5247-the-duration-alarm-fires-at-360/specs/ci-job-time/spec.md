## MODIFIED Requirements

### Requirement: The mean time of the test job over its last runs is checked
The `devops ci job-time` command SHALL read from the GitHub Actions API the time of a named check in the last completed `push` runs of a workflow on a branch. By default it SHALL read the check `Tests & Coverage` of `ci.yml` on `main`, 20 runs, with a limit of 360 seconds: the 300 seconds of AGENTS.md rule 5 and 60 seconds of tolerance for the variation of the runners. The command SHALL exit 0 when the mean of the runs is not over the limit, and exit 1 when it is. It SHALL print the time of each run read and the mean.

#### Scenario: The mean is inside the limit
- **WHEN** the last 20 runs of the job took 100 seconds each and the user runs `devops ci job-time`
- **THEN** the command exits 0 and the output names the mean of 100 seconds and the limit of 360 seconds

#### Scenario: The mean is over the target and inside the tolerance
- **WHEN** the last 20 runs of the job took 330 seconds each and the user runs `devops ci job-time`
- **THEN** the command exits 0

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

### Requirement: The workflow runs the check on main
The workflow `ci.yml` SHALL hold a job that runs `devops ci job-time --file-issue` on its daily schedule and on a manual run, and on no other event. No job SHALL wait for it. The job SHALL read the history of `main` with a token that can only read the repository contents and the Actions runs and write issues. The concurrency group of `ci.yml` SHALL hold the event name, so that a push to `main` does not cancel the schedule run.

#### Scenario: The daily schedule
- **WHEN** the schedule starts `ci.yml`
- **THEN** the run has a job `Test Job Duration` that runs `devops ci job-time --file-issue`

#### Scenario: A push to main
- **WHEN** a commit is pushed to `main`
- **THEN** the run has no job `Test Job Duration`, so the run is green when its other jobs pass

#### Scenario: A pull request
- **WHEN** a pull request is opened or updated
- **THEN** the run has no job `Test Job Duration`

#### Scenario: A push during the schedule run
- **WHEN** a commit is pushed to `main` while the schedule run of `ci.yml` runs
- **THEN** the push run is in another concurrency group, and the schedule run is not cancelled

## ADDED Requirements

### Requirement: A mean over the limit has one P0 issue
With `--file-issue` and a full read over the limit, the command SHALL comment on the lowest open issue whose body holds the line `<!-- devops-ci-job-time: <job> of <workflow> on <branch> -->` of the check, which an issue search for `devops-ci-job-time` finds. With no such open issue, it SHALL file one that ends with that line and has the labels `type/bug`, `scope/ci`, `status/new` and `priority/p0-critical`. It SHALL print the address of the issue and still exit 1.

#### Scenario: No open issue holds the alarm
- **WHEN** the mean of 20 runs is 400 seconds, and the only issue with the line of the check is closed, and the user runs `devops ci job-time --file-issue`
- **THEN** the command files one issue titled `fix(ci): Tests & Coverage averages 400 s, over the 360 s limit` with the four labels and a body that ends with the line, and exits 1

#### Scenario: An open issue holds the alarm
- **WHEN** the mean is over the limit and an open issue holds the line of the check under a title that a person changed
- **THEN** the command comments on that issue and files no issue

#### Scenario: An issue holds the alarm of another check
- **WHEN** the only open issues hold the line of another check or the word `devops-ci-job-time` in other text
- **THEN** they do not count as the alarm issue of the check

### Requirement: No issue request without a breach
With `--file-issue`, a mean inside the limit or a short read SHALL make no search and no write. A dry run SHALL list the search, the comment and the new issue, each with its condition, and make no request.

#### Scenario: No breach
- **WHEN** the mean is inside the limit, or only 3 of 20 runs could be read
- **THEN** the command searches no issue and writes nothing

#### Scenario: Dry run with the issue
- **WHEN** the user runs `devops ci job-time --file-issue --dry-run`
- **THEN** the plan lists the issue search, the comment and the new issue, and GitHub receives no request
