## ADDED Requirements

### Requirement: The stage job checks a stated CI job-time limit
Before it calls the planner, the stage job SHALL read the CI check name and the duration limit that the item body states, compare the limit with the mean of the check's last 20 runs on the default branch, and return the item to New with the evidence when the mean is over the limit. A mean equal to the limit SHALL pass. An item that states no limit SHALL make no job-time read.

#### Scenario: The body states a limit
- **WHEN** the body states that `Tests & Coverage` stays under 300 s
- **THEN** the parse returns the check `Tests & Coverage` and the limit 300 s

#### Scenario: The mean is over the limit
- **WHEN** the stated limit is 300 s and the last 20 runs average 328 s
- **THEN** the check reports the check, the mean, the sample size and the limit, and the item returns to New with no branch and no planner call

#### Scenario: The mean equals the limit
- **WHEN** the stated limit is 300 s and the mean is 300 s
- **THEN** the check reports no failure and the stage job stages the item

#### Scenario: The read fails twice
- **WHEN** the job-time read fails twice
- **THEN** the item stays Ready with the `ci_infra` failure and the job creates no branch and calls no planner
