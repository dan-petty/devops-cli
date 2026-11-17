## MODIFIED Requirements

### Requirement: Loki runs from the open-source chart at a release that fixes CVE-2026-21729
The chart source of Application `loki` in `k8s/argocd/apps/loki.yaml` SHALL be the repository `https://grafana-community.github.io/helm-charts` and the chart `loki`, at a chart version that runs Loki 3.7.0 or later, the first release that fixes CVE-2026-21729. The AppProject of the Application SHALL admit that repository. The `logging` stack of `devops k8s deploy-stack` SHALL add that repository and install the chart `grafana-community/loki` at the version of the Application.

#### Scenario: The Argo CD Application installs another chart
- **WHEN** a person runs `kubectl -n argocd get application loki`
- **THEN** the Application is `Synced` and `Healthy`, which Argo CD reports only for a source repository that the AppProject admits
- **AND** `kubectl -n logging get pod loki-0 -o jsonpath='{.status.containerStatuses[?(@.name=="loki")].image}'` names the image `grafana/loki` with a tag of 3.7.0 or later

#### Scenario: deploy-stack installs another chart
- **WHEN** a person runs `uv run devops k8s deploy-stack --stack logging --dry-run`
- **THEN** its `helm_commands` add the repository `grafana-community` at `https://grafana-community.github.io/helm-charts`
- **AND** they install `grafana-community/loki` with a `--version` equal to the `targetRevision` of Application `loki`

### Requirement: The chart version sets the Loki image
The chart source of Application `loki` SHALL give the chart the values file `k8s/logging/loki-values.yaml` and no other value: no `parameters`, `values` or `valuesObject`. `k8s/logging/loki-values.yaml` SHALL NOT set `loki.image` or `singleBinary.image`, which can set the tag or the digest of the Loki image. The chart then runs the Loki image of its `appVersion`.

#### Scenario: The values set an older Loki image tag
- **WHEN** a person runs `kubectl -n logging get pod loki-0 -o jsonpath='{.status.containerStatuses[?(@.name=="loki")].image}'` and `helm show chart loki --repo https://grafana-community.github.io/helm-charts --version <targetRevision>`, with the `targetRevision` of Application `loki`
- **THEN** the tag of the Loki image is equal to the `appVersion` of the chart
- **AND** a values file that sets `loki.image.tag` or `singleBinary.image.tag`, for example to 3.6.11, makes the two versions different

#### Scenario: The Application gives the chart another value
- **WHEN** a person runs `kubectl -n argocd get application loki -o jsonpath='{.spec.sources[0].helm}'`
- **THEN** the output holds only `valueFiles`, with the one file `$values/k8s/logging/loki-values.yaml`

### Requirement: The Loki values render no ServiceAccount that no pod uses
The Loki values SHALL set `memcached.enabled` to `false` while `chunksCache` and `resultsCache` are off, so the chart renders no `loki-memcached` ServiceAccount.

#### Scenario: the values turn the memcached objects off
- **WHEN** Argo CD has synced Application `loki`, and a person runs `kubectl -n logging get serviceaccounts,statefulsets`
- **THEN** the namespace holds no ServiceAccount `loki-memcached`
- **AND** it holds no StatefulSet `loki-chunks-cache` or `loki-results-cache`

## REMOVED Requirements

### Requirement: The Loki values set no key that the chart removed
**Reason**: The requirement restates a key that `k8s/logging/loki-values.yaml` must not hold. The chart reads no such key, so no validator or live check can see it, and only a test that reads the file can check it (#6083).
**Migration**: The values file holds no `monitoring.selfMonitoring` key. No other requirement holds the rule.

### Requirement: The Loki values name the documented deployment mode
**Reason**: The requirement restates a value and a comment of `k8s/logging/loki-values.yaml`, and its scenario reads the file. No validator or live check can tell the two names of the mode apart, because both give the same objects (#6083).
**Migration**: The values file keeps `deploymentMode: Monolithic`, and `kubectl -n logging get statefulsets` shows the one StatefulSet `loki` of that mode.
