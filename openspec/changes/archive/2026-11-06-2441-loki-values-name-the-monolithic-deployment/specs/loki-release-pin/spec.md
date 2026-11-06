## ADDED Requirements

### Requirement: The Loki values name the deployment mode that the chart documents
The Loki values SHALL set `deploymentMode` to `Monolithic`, and each comment of the values file that names the deployment mode SHALL name `Monolithic`.

#### Scenario: the values file names the current mode
- **WHEN** `k8s/logging/loki-values.yaml` is read
- **THEN** `deploymentMode` is `Monolithic` and no line holds `SingleBinary`

#### Scenario: the claim test accepts only the current mode
- **WHEN** `_loki_mode` in `tests/core/test_k8s_local_path_placement.py` gets a values dict whose `deploymentMode` is `SingleBinary`
- **THEN** the function calls `pytest.fail`

### Requirement: The Loki values render no ServiceAccount that no pod uses
The Loki values SHALL set `memcached.enabled` to `false` while `chunksCache` and `resultsCache` are off, so the chart renders no `loki-memcached` ServiceAccount.

#### Scenario: the values turn the memcached objects off
- **WHEN** `k8s/logging/loki-values.yaml` is read
- **THEN** `memcached.enabled` is `false`, and `chunksCache.enabled` and `resultsCache.enabled` are `false`
