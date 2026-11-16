# roadmap-job-grades Specification

## Purpose
The job grade of each roadmap workflow from the result line of each attempt in Loki: the grade table of the owner with one action for each grade, the ratio and its Wilson interval, and the report of `devops roadmap eval grades`.

## Requirements

### Requirement: The job grade is the floor of the ratio
The job grade of a workflow SHALL come from its attempts with `infra=false` in the window. Under 30 such attempts the grade SHALL be `too few`. With 30 or more, the grade SHALL be `100` when each attempt is a first pass, and else the highest floor that `p` reaches: `90` (0.90), `80` (0.80), `70` (0.70), `60` (0.60) or `<60`. The grade table SHALL live in one module, `roadmap/job_grade.py`.

#### Scenario: Too few attempts
- **WHEN** a workflow has 29 attempts, each a first-pass success
- **THEN** the grade is `too few`

#### Scenario: Each attempt a first pass
- **WHEN** a workflow has 30 attempts, each a first-pass success
- **THEN** the grade is `100`

#### Scenario: A line with no first-pass counts
- **WHEN** a workflow whose line has no count of fix rounds has 30 successes in 30 attempts
- **THEN** its first pass is not known and the grade is `90`

### Requirement: The report gives the point grade, the interval and the range
The report SHALL give the point grade of `p` at any count of attempts, the Wilson 95% interval of `p` from statsmodels, and the grades of the two bounds.

#### Scenario: 22 of 25 attempts
- **WHEN** a workflow has 22 successes in 25 attempts with `infra=false`
- **THEN** `p` is 0.88, the interval is [0.7004, 0.9583], the point grade is `80`, the range is `70` to `90`, and the grade is `too few`

### Requirement: An infrastructure cut counts in the share and not in the ratio
An attempt with `infra=true` SHALL count in the all-attempts ratio and in the infrastructure share, and not in `p`.

#### Scenario: An infrastructure cut
- **WHEN** a workflow has 22 successes in 25 attempts with `infra=false` and 1 attempt with `infra=true`
- **THEN** `p` is 0.88 and the infrastructure share is 0.0385

### Requirement: eval grades reads the result lines with metric instant queries
`devops roadmap eval grades` SHALL read the result lines with LogQL metric instant queries on `/loki/api/v1/query` of the Loki that `--loki-url` or `loki.url` names. `--repo` SHALL put a match of the repository in each query. `--dry-run` SHALL send no request and print each query.

#### Scenario: The dry run sends no request
- **WHEN** a person runs `devops roadmap eval grades --dry-run`
- **THEN** the command sends 0 requests and prints each LogQL query with the Loki address of `loki.url`

#### Scenario: Loki refuses a query
- **WHEN** Loki answers a query with HTTP 400
- **THEN** the report stops with `ServiceRequestError` and the status 400

### Requirement: The report gives the measures of each workflow and repository
For each workflow and repository the report SHALL give the counts, `p`, the interval and the grades, the first-pass ratio, the infrastructure share, the 3 largest failure classes, the action of the grade, the efficiency measures for a line with `tokens` and `seconds`, each version with 10 attempts or more, and the counts of 24 h and 6 h with the signals `broken` and `infra`. A job with no line SHALL get one row with no attempts.

#### Scenario: The report equals a hand count of recorded replies
- **WHEN** Loki answers each planned query with the recorded replies of `tests/fixtures/roadmap/job_grades/replies.json`
- **THEN** the row of each workflow and repository gives the counts, `p`, the interval, the grades, the top classes, the efficiency measures, the versions, the trend and the signals of the hand count

### Requirement: JSON gives one object for each workflow and repository
`devops roadmap eval grades --format json` SHALL print the report as one JSON object with the window, the repository of `--repo`, the Loki address and one object for each workflow and repository.

#### Scenario: The JSON report
- **WHEN** a person runs `devops roadmap eval grades --format json` on the recorded replies
- **THEN** the output is one JSON object whose `workflows` list has one object for each workflow and repository, with its grade

### Requirement: The docs generator writes the grade table into the job success page
`devops docs generate` SHALL write the grade table of `roadmap/job_grade.py` between the markers `<!-- JOB_GRADES_START -->` and `<!-- JOB_GRADES_END -->` of `docs/roadmap/job-success.md`, and `devops docs check` SHALL fail when the table on the page differs from the table of the code.

#### Scenario: A stale table on the page
- **WHEN** the block between the markers of the page holds another table
- **THEN** `devops docs check` names the page as out of date

### Requirement: The report reads the result lines of the Service and the Job pods, in both forms
Each query of `devops roadmap eval grades` SHALL select the containers `service`, `stage` and `fix-plan` of the namespace `devops`, SHALL count only a line that starts with `roadmap job result: ` after the parse, and SHALL parse a JSON line by its `message` field and a plain line as it is. A plain line SHALL NOT make Loki refuse a query. The base of the queries SHALL be one constant, and each query of the dashboard row `Roadmap Job Success` SHALL start with it.

#### Scenario: A JSON line of the Service and plain lines of two Job pods
- **WHEN** Loki holds one JSON line of the Service with `job=implement`, one plain line on stderr of a fix-plan Job pod with `job=fix_plan`, and one plain line on stderr of a stage Job pod with `job=stage`
- **THEN** the report gives 1 attempt to each of `implement`, `fix_plan` and `stage`

#### Scenario: A line in the log of a runner pod
- **WHEN** Loki also holds a plain result line in the container `runner` of a Job pod
- **THEN** the report does not count that line

#### Scenario: The dashboard reads the same lines
- **WHEN** a panel of the row `Roadmap Job Success` reads the result lines
- **THEN** its query starts with the base of the report
