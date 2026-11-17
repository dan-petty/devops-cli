# devcontainer-process-limit Specification

## Purpose
The process limit of the devcontainer: a burst of VS Code file searches must not fill the container and stop the tools of agent sessions.

## Requirements

### Requirement: Devcontainer process limit
The devcontainer configuration SHALL set the container process limit to at least 4096 with the `--pids-limit` option in `runArgs`, and SHALL keep `--gpus all` there.

#### Scenario: Run arguments hold the process limit
- **WHEN** a person runs `cat /sys/fs/cgroup/pids.max` and `nvidia-smi -L` in the workspace container on a host with a GPU
- **THEN** the process limit is 4096 or more
- **AND** `nvidia-smi -L` lists each GPU of the host
