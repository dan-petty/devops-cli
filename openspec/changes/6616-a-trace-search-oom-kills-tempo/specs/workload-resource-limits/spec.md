## ADDED Requirements

### Requirement: The Tempo query limits stay under the memory limit
The Tempo Helm values (`k8s/otel/tempo-values.yaml`) SHALL set `tempo.queryFrontend.search.max_bytes_per_trace` to `1000000`, `max_result_limit` to `50`, `max_duration` to `30s` and `target_bytes_per_second` to `25000000`, SHALL set `tempo.queryFrontend.max_outstanding_per_tenant` to `10` and `tempo.querier.max_concurrent_queries` to `4`, SHALL set `tempo.global_overrides.max_bytes_per_trace` to `1000000`, and SHALL keep the memory limit of the `tempo` container at `2048Mi`.

#### Scenario: The Tempo values hold each limit
- **WHEN** I run `uv run devops ci --check --only k8s` on `k8s/otel/tempo-values.yaml`
- **THEN** The row passes, and it fails when one of the seven limits or the `2048Mi` memory limit differs from the value that this requirement names.

#### Scenario: An edited limit fails the row
- **WHEN** I run `uv run devops ci --check --only k8s` after an edit sets `tempo.queryFrontend.max_outstanding_per_tenant` to `50`
- **THEN** The row fails and names `k8s/otel/tempo-values.yaml` and the key that differs.

#### Scenario: The outstanding searches fit under half of the memory limit
- **WHEN** I run `uv run devops ci --check --only k8s` on `k8s/otel/tempo-values.yaml`
- **THEN** The row passes, because ten outstanding searches of fifty results of `1000000` bytes hold 500000000 bytes, under the 1073741824 bytes of half of the `2048Mi` limit.

#### Scenario: The concurrent trace reads are bounded
- **WHEN** I run `uv run devops ci --check --only k8s` on `k8s/otel/tempo-values.yaml`
- **THEN** The row passes, because `tempo.querier.max_concurrent_queries` is `4`, no more than the `10` outstanding queries per tenant, and `4` times `tempo.global_overrides.max_bytes_per_trace` of `1000000` is 4000000 bytes, under the 1073741824 bytes of half of the `2048Mi` limit; it fails when the querier admits more concurrent queries than the outstanding-query limit.
