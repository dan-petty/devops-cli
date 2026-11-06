## ADDED Requirements

### Requirement: The policy admits only the sizes in the table
The policy SHALL refuse a Job of the Service unless the CPU request of its container equals the CPU limit, the pair of the CPU and the memory request is a row of `RUNNER_SIZES`, the container has a memory limit, and the value of `PYTEST_XDIST_AUTO_NUM_WORKERS` equals the CPU limit. It SHALL not pin the memory limit.

#### Scenario: A Job of each row
- **WHEN** a test builds the Job that the Service makes for each row of the table and evaluates the policy for the Service user
- **THEN** the policy admits the Job

#### Scenario: A size outside the table
- **WHEN** a test tries each pair of CPU and memory request from a grid that holds the rows and values near them
- **THEN** the policy admits exactly the pairs of the table

#### Scenario: A worker count that differs
- **WHEN** the Job sets `PYTEST_XDIST_AUTO_NUM_WORKERS` to a value other than its CPU limit, or sets a CPU request other than its CPU limit
- **THEN** the policy refuses the Job

#### Scenario: A raised memory limit
- **WHEN** the Job of a row sets a memory limit of 12Gi
- **THEN** the policy admits the Job
