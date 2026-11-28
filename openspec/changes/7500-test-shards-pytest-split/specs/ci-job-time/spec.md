## MODIFIED Requirements

### Requirement: Only the wanted runs are read
The command SHALL follow the next link of the listing of runs. The checks of one workflow, branch and count SHALL share one read, which asks for the jobs of each run one time. A read SHALL stop once each of its checks has its wanted runs, or once it read the jobs of 100 runs. The output of a short read SHALL name the bound of 100 runs. A `--runs` above 100 of `devops ci job-time` SHALL be a usage error that names the bound.

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

#### Scenario: A count above the bound
- **WHEN** the user runs `devops ci job-time --runs 101`
- **THEN** the command exits 2 with a usage error that names the bound of 100 runs, and sends no request
