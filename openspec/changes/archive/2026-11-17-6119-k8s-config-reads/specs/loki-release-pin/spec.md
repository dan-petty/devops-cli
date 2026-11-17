## MODIFIED Requirements

### Requirement: The chart version sets the Loki image
The chart source of Application `loki` SHALL give the chart the values file `k8s/logging/loki-values.yaml` and no other value: no `parameters`, `values` or `valuesObject`. `k8s/logging/loki-values.yaml` SHALL NOT set `loki.image` or `singleBinary.image`, which can set the tag or the digest of the Loki image. The chart then runs the Loki image of its `appVersion`.

#### Scenario: The values set an older Loki image tag
- **WHEN** `k8s/logging/loki-values.yaml` sets `loki.image.tag` or `singleBinary.image.tag`, for example to 3.6.11
- **THEN** a test that reads the values fails, although the chart pin did not change

#### Scenario: The Application gives the chart another value
- **WHEN** a person runs `kubectl -n argocd get application loki -o yaml` and `kubectl -n logging get statefulset loki -o jsonpath='{..image}'` on the cluster
- **THEN** the `helm` block of the chart source holds only `valueFiles` with `k8s/logging/loki-values.yaml`, and the image is the one of the chart release

## REMOVED Requirements

### Requirement: The Loki values name the deployment mode that the chart documents
**Reason**: Scenarios of this requirement described the test that read the manifests, which #6119 deletes (#6060).
**Migration**: The requirement "The Loki values name the documented deployment mode" holds the rule, with scenarios that name a live check or a validator command.

## ADDED Requirements

### Requirement: The Loki values name the documented deployment mode
The Loki values SHALL set `deploymentMode` to `Monolithic`, and each comment of the values file that names the deployment mode SHALL name `Monolithic`.

#### Scenario: the values file names the current mode
- **WHEN** `k8s/logging/loki-values.yaml` is read
- **THEN** `deploymentMode` is `Monolithic` and no line holds `SingleBinary`
