## MODIFIED Requirements

### Requirement: The memory limit of a runner Job stays 8 Gi
The runner Job that the Service creates SHALL have the memory limit of the setting `roadmap.implement.max_memory_limit`, whose default is 8Gi, whatever the deadline settings and the size of the plan are.

#### Scenario: The memory limit
- **WHEN** a round creates a Job and the setting is not set
- **THEN** the memory limit of its container is 8Gi

#### Scenario: A raised limit
- **WHEN** the setting is 12Gi and a round creates a Job
- **THEN** the memory limit of its container is 12Gi

## ADDED Requirements

### Requirement: The Service sizes the runner Job from the plan
The Service SHALL choose the CPU request, the CPU limit and the memory request of a runner Job from the table `RUNNER_SIZES` by the number of files that the plan names: the small row (CPU 1, memory 2Gi) for at most 10 files, and the large row (CPU 4, memory 6Gi) for more. The other values of the template SHALL stay.

#### Scenario: A plan with few files and a plan with many
- **WHEN** a round creates a Job for a plan whose tasks name 3 files, and another round creates a Job for a plan whose tasks name 12 files
- **THEN** the first Job requests 1 CPU and 2Gi, the second requests 4 CPU and 6Gi, and each keeps the `ephemeral-storage` of the template

### Requirement: The files of a plan are the paths in its tasks
The Service SHALL count the distinct file paths in the code spans of `tasks.md`, read at the revision that holds the plan: `origin/<default branch>` for a Planned item and `origin/<branch>` for a Staged item. A change that is archived at that revision SHALL count zero files.

#### Scenario: Paths are counted once
- **WHEN** the tasks name the same file in several tasks, and name commands and settings in code spans
- **THEN** the count holds each file path once and holds no command and no setting

#### Scenario: A Planned item
- **WHEN** the plan of a Planned item is on the default branch and names 11 files
- **THEN** the Job of the item has the large row

### Requirement: The worker count of a runner Job equals its CPU limit
The Service SHALL set `PYTEST_XDIST_AUTO_NUM_WORKERS` of the Job to the CPU limit of the same Job, and the CPU request SHALL equal the CPU limit.

#### Scenario: Every row
- **WHEN** a test reads each row of the table and the Job that the Service creates for it
- **THEN** the CPU request, the CPU limit and the value of `PYTEST_XDIST_AUTO_NUM_WORKERS` are equal

### Requirement: The size table cites its measurements
Each row of `RUNNER_SIZES` SHALL name the measured Job sample and its peak memory, and the memory request of the row SHALL be above that peak.

#### Scenario: The rows
- **WHEN** a test reads the table
- **THEN** each row has a sample name and a peak, and its memory request is above the peak

### Requirement: The memory limit is a setting that holds the largest request
The setting `roadmap.implement.max_memory_limit` SHALL have the default 8Gi and the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_MEMORY_LIMIT`. It SHALL be a whole number of Gi, and the configuration SHALL refuse a value below the largest memory request of the table.

#### Scenario: The default
- **WHEN** the configuration is loaded with no value
- **THEN** the setting is 8Gi

#### Scenario: A value below the largest request or in another form
- **WHEN** the setting is 5Gi, 8G or 8192Mi
- **THEN** the configuration is refused
