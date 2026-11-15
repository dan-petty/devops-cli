## ADDED Requirements

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
