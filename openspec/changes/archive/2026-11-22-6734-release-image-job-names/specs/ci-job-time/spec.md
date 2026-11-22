## MODIFIED Requirements

### Requirement: The release image jobs of the release workflow are checked
The `devops ci job-time` command SHALL read the jobs `Build`, `Verify` and `Attest & Tag` of `MCP Server Image` and of `Runner Image`, which the Actions API names `<image> / <job>`, such as `Runner Image / Build`, in `release.yml` on `main` over their last 10 completed runs. Each job SHALL be one check with a limit of 360 seconds. The command SHALL print the mean of each job and SHALL exit 1 when a mean is over its limit or a read is short.

#### Scenario: Both release image jobs are measured
- **WHEN** the last 10 release runs give the three jobs of both images their own times, the runs between them hold only skipped jobs and `${{ matrix.title }} Image`, and the test job is inside its limit
- **THEN** the output names the mean of each of the six jobs, and the command exits 0

#### Scenario: A release image job over the limit files one P0 issue
- **WHEN** the last 10 release runs give `Runner Image / Verify` 380 seconds each, every other check is inside its limit, and the user runs `devops ci job-time --file-issue`
- **THEN** the command files one issue titled `fix(ci): Runner Image / Verify averages 380 s, over the 360 s limit` with the labels `type/bug`, `scope/ci`, `status/new` and `priority/p0-critical`, and exits 1

#### Scenario: A mean at the limit files no issue
- **WHEN** each of the last 10 runs of `Runner Image / Build` took 360 seconds, every other check is inside its limit, and the user runs `devops ci job-time --file-issue`
- **THEN** the command exits 0 and makes no issue request

#### Scenario: A short read of the release runs never passes
- **WHEN** only 2 completed runs of the release workflow hold the release image jobs, and the user runs `devops ci job-time --file-issue`
- **THEN** the command exits 1, its output says that only 2 of the last 10 runs of `MCP Server Image / Build` were read, and it makes no issue request

#### Scenario: An option reads one check
- **WHEN** the user runs `devops ci job-time --workflow release.yml --job "Runner Image / Build" --runs 5` and the last 5 release runs gave that job 200 seconds each
- **THEN** the command prints one mean of 200 seconds, reads no other job, and exits 0

### Requirement: Only the wanted runs are read
The command SHALL follow the next link of the listing of runs. The checks of one workflow, branch and count SHALL share one read, which asks for the jobs of each run one time. A read SHALL stop once each of its checks has its wanted runs, or once it read the jobs of 100 runs. The output of a short read SHALL name the bound of 100 runs.

#### Scenario: A second page of runs
- **WHEN** the listing links a next page
- **THEN** the runs of the next page count when the first page holds fewer than the wanted runs

#### Scenario: No more requests than needed
- **WHEN** the listing holds 12 runs and 10 are wanted
- **THEN** the command asks for the jobs of the first 10 runs only

#### Scenario: One read for the checks of one workflow
- **WHEN** the command reads the six release image checks of `release.yml` on `main`
- **THEN** it lists the runs one time and asks for the jobs of each run one time

#### Scenario: No run holds the job
- **WHEN** the listing of `release.yml` holds 150 runs on two pages, and no run holds a release image job
- **THEN** the command asks for the jobs of the first 100 runs only, reads no second page, exits 1, and its output names the bound of 100 runs
