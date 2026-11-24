# k8s-helper-images Specification

## Purpose

Helper pods and evaluation containers read images from Kubernetes CronJob manifests and packaged files so that automated dependency managers track their versions.

## Requirements

### Requirement: Probe image from template
The service probe SHALL read the BusyBox image and the pod and container security contexts from suspended CronJob `devops/service-probe` in the cluster.

#### Scenario: Probe pod uses template image
- **WHEN** a unit test answers the CronJob read with a body whose `probe` container names a BusyBox tag and digest and a restricted security context, and the test builds the probe pod
- **THEN** the pod image, the pod security context and the container security context equal those of the template

### Requirement: Volume move image from template
The volume move command and its measure step SHALL read the Debian image from suspended CronJob `devops/volume-move` in the cluster.

#### Scenario: Volume move pods use template image
- **WHEN** a unit test answers the CronJob read with a body whose `copy` container names a Debian tag and digest and builds the source, destination and measure pods
- **THEN** every pod container image equals the template image, and no pod carries the template restricted security context

### Requirement: Missing template error
A command that needs a template MUST fail with an error that names the missing CronJob and its namespace `devops` when the cluster has none.

#### Scenario: Missing template CronJob
- **WHEN** the cluster returns an empty body for the template read
- **THEN** the command raises `ServiceProbeError` or `VolumeMoveError` naming `devops/service-probe` or `devops/volume-move`

### Requirement: Shipped harbor Dockerfile
The harbor evaluation task SHALL read the base and uv lines from the shipped Dockerfile `src/devops_cli/roadmap/implement/harbor/Dockerfile`.

#### Scenario: Harbor task uses shipped Dockerfile
- **WHEN** `generate_task` runs for a harbor case
- **THEN** the task `Dockerfile` starts with the exact lines of the shipped file, including digest pins for Python and uv
