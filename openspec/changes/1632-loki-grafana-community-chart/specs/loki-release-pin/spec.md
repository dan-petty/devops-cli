# loki-release-pin Specification

## Purpose

The Helm chart and the Loki release that the logging stack runs. Argo CD and `devops k8s deploy-stack --stack logging` install one open-source Loki chart at one version, and that version runs a Loki release that CVE-2026-21729 does not affect.

## ADDED Requirements

### Requirement: Loki runs from the open-source chart at a release that fixes CVE-2026-21729
The chart source of Application `loki` in `k8s/argocd/apps/loki.yaml` SHALL be the repository `https://grafana-community.github.io/helm-charts`, the chart `loki` and the version 20.0.2, and the AppProject of the Application SHALL admit that repository. The `logging` stack of `devops k8s deploy-stack` SHALL add that repository and install the chart `grafana-community/loki` at the same version. Chart 20.0.2 runs Loki 3.7.9, and Loki 3.7.0 is the first release that fixes CVE-2026-21729.

#### Scenario: The Argo CD Application installs another chart
- **WHEN** a test reads the chart source of Application `loki` and the AppProject that the Application names
- **THEN** the repository is `https://grafana-community.github.io/helm-charts`, the chart is `loki` and the version is 20.0.2
- **AND** the `sourceRepos` of the AppProject hold that repository

#### Scenario: deploy-stack installs another chart
- **WHEN** a test reads the one Helm release of the `logging` stack and the Helm repositories of that stack
- **THEN** the release installs `grafana-community/loki` at version 20.0.2
- **AND** the repository `grafana-community` of the stack is `https://grafana-community.github.io/helm-charts`

### Requirement: The Loki values set no key that the chart removed
`k8s/logging/loki-values.yaml` SHALL NOT set `monitoring.selfMonitoring`, which the grafana-community chart removed in 9.0.0.

#### Scenario: The values set the removed self-monitoring block
- **WHEN** a test reads `k8s/logging/loki-values.yaml`
- **THEN** the values have no `monitoring.selfMonitoring` key
