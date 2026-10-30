# roadmap-service-deployment Specification

## Purpose
How the roadmap Service and the cluster Jobs run in namespace `devops`: the replica count of `deployment/roadmap-service`, and the model retry count of ConfigMap `devops-cli-config`, which both read.

## Requirements

### Requirement: The Service runs as one pod
`deployment/roadmap-service` SHALL set `replicas: 1` and the `Recreate` strategy, so one pod of the Service runs at a time.

#### Scenario: The manifest is read
- **WHEN** `k8s/devops/roadmap-service/deployment.yaml` is read
- **THEN** its `spec.replicas` is 1 and its `spec.strategy.type` is `Recreate`

### Requirement: A model call in the cluster is sent at most two times
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set `ai.max_retries` to 1, and the ConfigMap that a deploy renders from it SHALL keep that value.

#### Scenario: A deploy renders the ConfigMap from the repository's template
- **WHEN** the active config sets `service.repos` and the App's settings, and the ConfigMap is rendered from `k8s/devops/configmap.example.yaml`
- **THEN** the rendered config validates as settings with `ai.model` `devops-background` and `ai.max_retries` 1

### Requirement: The Service image runs the pinned OpenSpec
The service stage of `Dockerfile` SHALL carry the `node` binary of a digest-pinned `node` image whose major version is the one in `.node-version`, and the OpenSpec that `devops install-tools --tool openspec` installs from the lockfile of `src/devops_cli/tools_lock/openspec`. The directory of its `openspec` link SHALL be on the `PATH` of the stage. The stage SHALL set `OPENSPEC_TELEMETRY=0`, `OPENSPEC_NO_UPDATE_CHECK=1` and `DO_NOT_TRACK=1`.

#### Scenario: OpenSpec comes from the lockfile
- **WHEN** the builder stage and the service stage of `Dockerfile` are read
- **THEN** the builder stage runs `devops install-tools --tool openspec` with a `--target-dir`, the service stage copies the tool directory from the builder to the same path, and that `--target-dir` is on the `PATH` of the service stage

#### Scenario: The telemetry is off
- **WHEN** the environment of the service stage is read
- **THEN** it sets `OPENSPEC_TELEMETRY` to 0, `OPENSPEC_NO_UPDATE_CHECK` to 1 and `DO_NOT_TRACK` to 1

#### Scenario: The Node runtime is the one of CI
- **WHEN** the `node` stage of `Dockerfile` is read
- **THEN** its image is pinned by digest and its major version equals the content of `.node-version`, and the builder stage and the service stage copy the `node` binary from it

### Requirement: A deploy keeps the hourly request budget
The ConfigMap that a deploy renders SHALL hold `service.github_requests_per_hour` when the active settings set it, and SHALL hold no such key when they do not.

#### Scenario: The active settings set the budget
- **WHEN** the active settings set `service.github_requests_per_hour` to 2000 and the ConfigMap is rendered
- **THEN** the `service` section of the rendered config holds `github_requests_per_hour: 2000`

#### Scenario: The active settings keep the default
- **WHEN** the active settings set no `service.github_requests_per_hour` and the ConfigMap is rendered
- **THEN** the `service` section of the rendered config holds no `github_requests_per_hour`
