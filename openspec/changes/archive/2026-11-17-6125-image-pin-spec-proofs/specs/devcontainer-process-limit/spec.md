## MODIFIED Requirements

### Requirement: Devcontainer process limit
The devcontainer configuration SHALL set the container process limit to at least 4096 with the `--pids-limit` option in `runArgs`, and SHALL keep `--gpus all` there.

#### Scenario: Run arguments hold the process limit
- **WHEN** a person runs `cat /sys/fs/cgroup/pids.max` and `nvidia-smi -L` in the workspace container on a host with a GPU
- **THEN** the process limit is 4096 or more
- **AND** `nvidia-smi -L` lists each GPU of the host

## REMOVED Requirements

### Requirement: Process limit guard
**Reason**: The requirement asked for a test that reads `--pids-limit` from `.devcontainer/devcontainer.json`. #6075 deleted that test and its reader under #6060, so no source code holds the reader that the scenario names (#6083).
**Migration**: The requirement "Devcontainer process limit" reads the limit of the running container with `cat /sys/fs/cgroup/pids.max`.
