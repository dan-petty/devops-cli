## MODIFIED Requirements

### Requirement: The policy admits only the sizes in the table
The policy SHALL refuse a Job of the Service unless the CPU request of its container equals the CPU limit, the memory request equals the memory limit, the pair of the CPU and the memory is a row of `RUNNER_SIZES`, and the value of `PYTEST_XDIST_AUTO_NUM_WORKERS` equals the CPU limit.

#### Scenario: A Job of each row
- **WHEN** the gate check `tests/gate/k8s_checks/job_admission_policy.py` (`uv run devops ci --check --only k8s`) builds the Job that the Service makes for each row of the table and evaluates the policy for the Service user
- **THEN** the policy admits the Job

#### Scenario: A size outside the table
- **WHEN** the gate check tries each pair of CPU and memory, with each limit equal to its request, from a grid that holds the rows and values near them
- **THEN** the policy admits exactly the pairs of the table

#### Scenario: A worker count that differs
- **WHEN** the Job sets `PYTEST_XDIST_AUTO_NUM_WORKERS` to a value other than its CPU limit, or sets a CPU request other than its CPU limit
- **THEN** the policy refuses the Job

#### Scenario: A raised memory limit
- **WHEN** the Job of the small row sets a memory limit of 16Gi, above its memory request
- **THEN** the policy refuses the Job with the message of the size table

#### Scenario: A memory limit below the request or no memory limit
- **WHEN** the Job of the small row sets a memory limit of 4Gi, or sets no memory limit
- **THEN** the policy refuses the Job with the message of the size table
