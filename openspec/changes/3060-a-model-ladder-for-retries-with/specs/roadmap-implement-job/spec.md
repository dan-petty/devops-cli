## MODIFIED Requirements

### Requirement: The job record
The job SHALL keep `implement.group` (the last group that passed), `implement.sha` (the commit it ended on), `implement.branch` (the branch of the pull request), `implement.pr` (the pull request), `implement.stopped` and `implement.spend` in the job record of the item. The spend SHALL be the requests, input tokens and output tokens of every step the job ran, itemized per model tier and aggregated in total.

#### Scenario: Spend
- **WHEN** two steps used 3 and 4 requests
- **THEN** the record of the spend holds 7 requests

#### Scenario: Spend itemized per tier
- **WHEN** two steps ran on tier `devops-coder` and tier `devops-reasoning`
- **THEN** the record of the spend holds the token count for each tier and the aggregate total

#### Scenario: The branch
- **WHEN** the job takes a Staged item and a Planned item to a ready pull request
- **THEN** the record of each holds its branch and its pull request
