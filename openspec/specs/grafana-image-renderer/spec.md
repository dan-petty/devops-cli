# grafana-image-renderer Specification

## Purpose
The image renderer of the Grafana in the monitoring stack, which gives a PNG of a panel or a dashboard to the render API of Grafana, to the Grafana MCP tool and to alerts, and the token that Grafana sends to it.

## Requirements

### Requirement: Grafana runs the image renderer of its chart at a release tag
The Grafana values SHALL enable the `imageRenderer` of the `grafana` chart with the image `grafana/grafana-image-renderer` at a release tag `v<major>.<minor>.<patch>` and the pull policy `IfNotPresent`, with CPU and memory requests and limits, a `GOMEMLIMIT` below the memory limit, and the ingress NetworkPolicy of the chart.

#### Scenario: The image and the resources
- **WHEN** a person runs `uv run devops k8s image-pins` and `kubectl -n monitoring rollout status deployment/grafana-image-renderer`
- **THEN** the command resolves the renderer image at its release tag, and the rollout completes
- **AND** `uv run devops prometheus query 'kube_pod_container_status_last_terminated_reason{namespace="monitoring",reason="OOMKilled"}'` returns no series of the renderer, because `GOMEMLIMIT` holds the heap below the limit

### Requirement: The chart connects Grafana and the renderer by their Services
The Grafana values SHALL set no `imageRenderer.serverURL` and no `imageRenderer.renderingCallbackURL`, so that the chart gives Grafana the Service DNS name of the renderer and gives the renderer the Grafana Service. The values SHALL set no `imageRenderer.token`, and `imageRenderer.existingSecret` SHALL be `grafana-image-renderer`.

#### Scenario: The URLs and the token
- **WHEN** a person runs `kubectl -n monitoring port-forward svc/grafana 3000:80` and sends `GET /render/d-solo/<dashboard>?panelId=<panel>` with a Grafana session to the local port
- **THEN** Grafana answers 200 with an `image/png` body, so Grafana reached the renderer, the renderer reached Grafana, and both hold the same token

### Requirement: No Ingress routes to the image renderer
No Ingress under `k8s/` SHALL name the Service `grafana-image-renderer` as a backend.

#### Scenario: The Ingress backends
- **WHEN** a person runs `kubectl get ingress --all-namespaces -o wide`
- **THEN** no backend names the Service `grafana-image-renderer`, and a backend names the Service `grafana`

### Requirement: The renderer token comes from the keyring
The cluster Secret table SHALL hold the row `monitoring/grafana-image-renderer` of stack `infra` with the key `token`, read from the keyring-only key `grafana_renderer_token`, adopted from the live value or else generated with `token_urlsafe(32)`. A change of the row SHALL restart `deployment/grafana` and `deployment/grafana-image-renderer`. `k8s/README.md` SHALL list the row, and the dry run of `devops k8s deploy-stack --stack infra` SHALL list `monitoring/grafana-image-renderer: token`.

#### Scenario: The table row
- **WHEN** a test reads the cluster Secret table
- **THEN** the row `monitoring/grafana-image-renderer` has the key `token` in stack `infra`, with a `urlsafe` generator of 32 bytes, and the restart targets `deployment/grafana` and `deployment/grafana-image-renderer`
- **AND** the keyring-only keys of the table include `grafana_renderer_token`

#### Scenario: Each restart target exists
- **WHEN** a person runs `kubectl -n monitoring get deployment grafana grafana-image-renderer`
- **THEN** both restart targets of the row exist on the cluster

#### Scenario: The dry run lists the Secret
- **WHEN** `devops k8s deploy-stack --stack infra` runs as a dry run
- **THEN** the Secrets that it lists include `monitoring/grafana-image-renderer: token`

### Requirement: The image renderer pod mounts no ServiceAccount token
The Grafana values SHALL leave `imageRenderer.automountServiceAccountToken` false, because the renderer calls no Kubernetes API.

#### Scenario: The renderer pod has no token
- **WHEN** a person runs `kubectl -n monitoring get pods -l app.kubernetes.io/name=grafana-image-renderer -o jsonpath='{..volumeMounts[*].mountPath}'`
- **THEN** no mount path is `/var/run/secrets/kubernetes.io/serviceaccount`

### Requirement: A missing renderer token stops only panel images
The Grafana container SHALL read `GF_RENDERING_RENDERER_TOKEN` through a `secretKeyRef` with `optional: true`, so Grafana starts when Secret `monitoring/grafana-image-renderer` is missing. The renderer Deployment SHALL keep a required reference. `OPTIONAL_FEATURE_SECRETS` SHALL name `monitoring/grafana-image-renderer`, and `k8s/README.md` SHALL say that a pull request which adds a Secret reference names the push command as its first line.

#### Scenario: The rendered Grafana pod
- **WHEN** `helm template` renders the Grafana chart with `k8s/monitoring/grafana-values.yaml`
- **THEN** the last entry of `GF_RENDERING_RENDERER_TOKEN` of the Grafana container holds `optional: true`

#### Scenario: The renderer pod
- **WHEN** the chart renders the renderer Deployment
- **THEN** its token reference holds no `optional` field

#### Scenario: The list
- **WHEN** a test reads `OPTIONAL_FEATURE_SECRETS`
- **THEN** it holds `monitoring/grafana-image-renderer`, and the cluster Secret table holds that Secret
