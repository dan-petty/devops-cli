## Purpose
The image renderer of the Grafana in the monitoring stack, which gives a PNG of a panel or a dashboard to the render API of Grafana, to the Grafana MCP tool and to alerts, and the token that Grafana sends to it.

## ADDED Requirements

### Requirement: Grafana runs the image renderer of its chart at a release tag
The Grafana values SHALL enable the `imageRenderer` of the `grafana` chart with the image `grafana/grafana-image-renderer` at a release tag `v<major>.<minor>.<patch>` and the pull policy `IfNotPresent`, with CPU and memory requests and limits, a `GOMEMLIMIT` below the memory limit, and the ingress NetworkPolicy of the chart.

#### Scenario: The image and the resources
- **WHEN** a test reads `imageRenderer` of `k8s/monitoring/grafana-values.yaml`
- **THEN** it is enabled, its image is `grafana/grafana-image-renderer` at a release tag with `IfNotPresent`, its requests and its limits each name `cpu` and `memory`, the memory request is not above the memory limit, `GOMEMLIMIT` is above zero and below the memory limit, and `networkPolicy.limitIngress` is true

### Requirement: The chart connects Grafana and the renderer by their Services
The Grafana values SHALL set no `imageRenderer.serverURL` and no `imageRenderer.renderingCallbackURL`, so that the chart gives Grafana the Service DNS name of the renderer and gives the renderer the Grafana Service. The values SHALL set no `imageRenderer.token`, and `imageRenderer.existingSecret` SHALL be `grafana-image-renderer`.

#### Scenario: The URLs and the token
- **WHEN** a test reads `imageRenderer` of `k8s/monitoring/grafana-values.yaml`
- **THEN** `serverURL`, `renderingCallbackURL` and `token` are empty, and `existingSecret` is `grafana-image-renderer`

### Requirement: No Ingress routes to the image renderer
No Ingress under `k8s/` SHALL name the Service `grafana-image-renderer` as a backend.

#### Scenario: The Ingress backends
- **WHEN** a test reads the Service of each backend of each Ingress under `k8s/`
- **THEN** no backend names `grafana-image-renderer`, and a backend names `grafana`

### Requirement: The renderer token comes from the keyring
The cluster Secret table SHALL hold the row `monitoring/grafana-image-renderer` of stack `infra` with the key `token`, read from the keyring-only key `grafana_renderer_token`, adopted from the live value or else generated with `token_urlsafe(32)`. A change of the row SHALL restart `deployment/grafana` and `deployment/grafana-image-renderer`. `k8s/README.md` SHALL list the row, and the dry run of `devops k8s deploy-stack --stack infra` SHALL list `monitoring/grafana-image-renderer: token`.

#### Scenario: The table row
- **WHEN** a test reads the cluster Secret table
- **THEN** the row `monitoring/grafana-image-renderer` has the key `token` in stack `infra`, with a `urlsafe` generator of 32 bytes, and the restart targets `deployment/grafana` and `deployment/grafana-image-renderer`
- **AND** the keyring-only keys of the table include `grafana_renderer_token`

#### Scenario: Each restart target exists
- **WHEN** a test compares the restart targets of the table with the manifest workloads, the Helm releases and the chart workloads that the values turn on
- **THEN** `deployment/grafana-image-renderer` is a chart workload that `imageRenderer.enabled` turns on

#### Scenario: The dry run lists the Secret
- **WHEN** `devops k8s deploy-stack --stack infra` runs as a dry run
- **THEN** the Secrets that it lists include `monitoring/grafana-image-renderer: token`

### Requirement: The image renderer pod mounts no ServiceAccount token
The Grafana values SHALL leave `imageRenderer.automountServiceAccountToken` false, because the renderer calls no Kubernetes API.

#### Scenario: The renderer pod has no token
- **WHEN** a test reads the token use of each chart pod from the values
- **THEN** the pod `image-renderer` of `k8s/monitoring/grafana-values.yaml` mounts no token
