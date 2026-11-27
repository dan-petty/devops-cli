## MODIFIED Requirements

### Requirement: The Service sizes the runner Job from the plan
The Service SHALL choose the CPU and the memory of the container `agent` of a runner Job from the table `RUNNER_SIZES` by the number of files that the plan names: the small row (CPU 1, memory 5Gi) for at most 10 files, and the large row (CPU 4, memory 11Gi) for more. The CPU limit SHALL equal the CPU request, and the memory limit SHALL equal the memory request. `prepare` and `publish` SHALL keep the small row of the template, and the other values of the template SHALL stay.

#### Scenario: A plan with few files and a plan with many
- **WHEN** a round creates a Job for a plan whose tasks name 3 files, and another round creates a Job for a plan whose tasks name 12 files
- **THEN** the first Job requests and limits 1 CPU and 5Gi, the second requests and limits 4 CPU and 11Gi, and each keeps the `ephemeral-storage` of the template

#### Scenario: Every row
- **WHEN** a test reads the resources of each row of the table
- **THEN** the limits of each row are equal to its requests

### Requirement: The size table cites its measurements
Each row of `RUNNER_SIZES` SHALL name the measured Job sample and its peak memory, and the peak SHALL be at most 80 % of the memory of the row, the room of T1 in the Kubernetes guideline.

#### Scenario: The rows
- **WHEN** a test reads the table
- **THEN** each row has a sample name and a peak, and its peak is at most 80 % of its memory

## REMOVED Requirements

### Requirement: The memory limit of a runner Job stays 8 Gi
**Reason**: The memory limit of a runner Job equals the memory request of its row (#7422). A limit above the request let the scheduler place a Job on a node that could not hold the limit.
**Migration**: The requirement "The Service sizes the runner Job from the plan" gives the limit of each row.

### Requirement: The memory limit is a setting that holds the largest request
**Reason**: The setting `roadmap.implement.max_memory_limit` is removed with its variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_MEMORY_LIMIT`. The rows of `RUNNER_SIZES` give the limit (#7422).
**Migration**: The section `roadmap.implement` ignores the key, so a config file that still holds it loads. Remove the key from the config file.

### Requirement: The description of the memory limit names the node that runs the Job
**Reason**: The setting is removed (#7422).
**Migration**: None.

### Requirement: The cluster document states both runner memory limits
**Reason**: The setting is removed, so the code default and the value of the example ConfigMap are gone (#7422).
**Migration**: The Size section of `docs/CLUSTER.md` gives the memory of each row.
