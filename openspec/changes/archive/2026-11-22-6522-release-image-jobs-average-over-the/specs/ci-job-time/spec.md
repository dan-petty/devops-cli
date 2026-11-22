## ADDED Requirements

### Requirement: The release image jobs of the release workflow are checked
The `devops ci job-time` command SHALL read the jobs `MCP Server Image` and `Runner Image` of `release.yml` on `main` over their last 10 completed runs, each with a limit of 360 seconds: 300 seconds and 60 seconds of tolerance. It SHALL print the mean of each job and SHALL exit 1 when a mean is over its limit or when fewer than 10 completed runs hold the job. With `--file-issue` it SHALL file one P0 issue for a job whose mean is over the limit.

#### Scenario: Both release image jobs are measured
- **WHEN** The last 10 completed runs of the release workflow give each of `MCP Server Image` and `Runner Image` 300 seconds, and the test job is inside its limit
- **THEN** The output names a mean of 300 seconds for `MCP Server Image` and for `Runner Image`, and the command exits 0

#### Scenario: A release image job over the limit files one P0 issue
- **WHEN** The last 10 completed runs give `MCP Server Image` 380 seconds each, `Runner Image` and the test job are inside their limits, and the user runs `devops ci job-time --file-issue`
- **THEN** The command files one issue titled `fix(ci): MCP Server Image averages 380 s, over the 360 s limit` with the labels `type/bug`, `scope/ci`, `status/new` and `priority/p0-critical`, and exits 1

#### Scenario: A mean at the limit files no issue
- **WHEN** Each of the last 10 runs of `Runner Image` took 360 seconds and every other check is inside its limit, and the user runs `devops ci job-time --file-issue`
- **THEN** The command exits 0 and files no issue

#### Scenario: A short read of the release runs never passes
- **WHEN** Only 2 completed runs of the release workflow hold `Runner Image`
- **THEN** The command exits 1 and its output says that only 2 of the last 10 runs were read

#### Scenario: An option reads one check
- **WHEN** The user runs `devops ci job-time --workflow release.yml --job "Runner Image" --runs 5` and the last 5 runs of that job took 200 seconds each
- **THEN** The command prints one mean of 200 seconds, reads no other job, and exits 0
