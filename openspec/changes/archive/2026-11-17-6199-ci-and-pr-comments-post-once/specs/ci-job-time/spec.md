## MODIFIED Requirements

### Requirement: A mean over the limit has one P0 issue
With `--file-issue` and a full read over the limit, the command SHALL write its report into the lowest open issue whose body holds the line `<!-- devops-ci-job-time: <job> of <workflow> on <branch> -->` of the check, which an issue search for `devops-ci-job-time` finds. With none open, it SHALL file one that holds the report and ends with that line, with the labels `type/bug`, `scope/ci`, `status/new` and `priority/p0-critical`. It SHALL print the address of the issue and still exit 1.

#### Scenario: No open issue holds the alarm
- **WHEN** the mean of 20 runs is 400 seconds, and the only issue with the line of the check is closed, and the user runs `devops ci job-time --file-issue`
- **THEN** the command files one issue titled `fix(ci): Tests & Coverage averages 400 s, over the 360 s limit` with the four labels and a body that ends with the line, and exits 1

#### Scenario: An open issue holds the alarm
- **WHEN** the mean is over the limit and an open issue holds the line of the check under a title that a person changed
- **THEN** the command writes the report into the body of that issue, posts no comment and files no issue

#### Scenario: An issue holds the alarm of another check
- **WHEN** the only open issues hold the line of another check or the word `devops-ci-job-time` in other text
- **THEN** they do not count as the alarm issue of the check

### Requirement: No issue request without a breach
With `--file-issue`, a mean inside the limit or a short read SHALL make no search and no write. A dry run SHALL list the search, the read and the change of the body of the open issue, and the new issue, each with its condition, and make no request. It SHALL list no comment.

#### Scenario: No breach
- **WHEN** the mean is inside the limit, or only 3 of 20 runs could be read
- **THEN** the command searches no issue and writes nothing

#### Scenario: Dry run with the issue
- **WHEN** the user runs `devops ci job-time --file-issue --dry-run`
- **THEN** the plan lists the issue search, the `GET` and the `PATCH` of the issue, and the new issue, lists no comment, and GitHub receives no request

## ADDED Requirements

### Requirement: The alarm issue holds the report one time
The report SHALL be between the lines `<!-- devops ci job-time report: start -->` and `<!-- devops ci job-time report: end -->` in the body of the alarm issue. A run SHALL read the body of the open issue from GitHub, replace only the report in it, or add the report at its end when it holds none, and keep the alarm line and all other text. It SHALL post no comment, and SHALL send no change when the body already holds the same report.

#### Scenario: A later run replaces the report
- **WHEN** the run of one day filed the issue with a mean of 400 seconds, a person then added text above and below the report, and the run of the next day reads a mean of 500 seconds
- **THEN** the body holds one report, with the mean of 500 seconds, and the text of the person and the alarm line stay

#### Scenario: The same report
- **WHEN** the body of the open issue already holds the report that the run makes
- **THEN** the command sends no change and posts no comment
