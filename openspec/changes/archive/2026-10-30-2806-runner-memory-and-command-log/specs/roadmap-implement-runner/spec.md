# Spec Delta

## MODIFIED Requirements

### Requirement: A suspended CronJob is the template of the runner Job
CronJob `devops-cli-runner` in namespace `devops` SHALL be suspended and SHALL never run on a schedule. Its Job template SHALL name the image `ghcr.io/dan-petty/devops-cli/runner` with no tag, request and limit 2 CPU, request 4 Gi and limit 8 Gi of memory, request 2 Gi and limit 6 Gi of `ephemeral-storage`, set `activeDeadlineSeconds` to 7200 and `backoffLimit` to 0, and use the `securityContext` of CronJob `devops-cli`. Its pod SHALL use ServiceAccount `devops-cli`, which mounts no token.

#### Scenario: The manifest is read
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** CronJob `devops-cli-runner` holds the values above, its container is named `runner`, its pod mounts no ServiceAccount token, its root filesystem is read-only, and its capabilities drop `ALL`

#### Scenario: The admission policy
- **WHEN** a test runs the expressions of policy `roadmap-service-jobs` against the Job that the template makes
- **THEN** no expression refuses it

## ADDED Requirements

### Requirement: The runner Job bounds the workers of the test runner to its CPU limit
The container of CronJob `devops-cli-runner` SHALL set `PYTEST_XDIST_AUTO_NUM_WORKERS` to the number of its CPU limit. `pytest-xdist` counts the CPUs of the node, not the CPU limit of the pod, so without the variable a test run starts one worker for each CPU of the node.

#### Scenario: The variable
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** the variable of the runner container equals its CPU limit
