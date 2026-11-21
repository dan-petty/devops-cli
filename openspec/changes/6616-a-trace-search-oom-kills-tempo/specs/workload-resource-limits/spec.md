## ADDED Requirements

### Requirement: The Tempo query limits stay under the memory limit
The Tempo Helm values (`k8s/otel/tempo-values.yaml`) SHALL set the search limits of the query frontend, the outstanding searches per tenant and the querier concurrency limit under the `2048Mi` memory limit of the container `tempo`, and SHALL cut every trace above `1000000` bytes when Tempo pushes it.

#### Scenario: The limits and their values
- **WHEN** I run `uv run devops ci --check --only k8s`
- **THEN** The row passes only when `k8s/otel/tempo-values.yaml` sets `tempo.queryFrontend.search.max_bytes_per_trace` to `1000000`, `tempo.queryFrontend.search.max_result_limit` to `50`, `tempo.queryFrontend.search.max_duration` to `30s`, `tempo.queryFrontend.search.target_bytes_per_second` to `25000000`, `tempo.queryFrontend.max_outstanding_per_tenant` to `10`, `tempo.querier.max_concurrent_queries` to `4` and `tempo.global_overrides.max_bytes_per_trace` to `1000000`.

#### Scenario: The k8s row passes on the Tempo limits
- **WHEN** I run `uv run devops ci --check --only k8s`
- **THEN** The row passes and reports no failure for `k8s/otel/tempo-values.yaml`.

#### Scenario: The outstanding searches fit the memory limit
- **WHEN** I run `uv run devops ci --check --only k8s` on values whose ten outstanding searches hold fifty results of one million bytes each
- **THEN** The row passes, because 500000000 bytes stay under the 1073741824 bytes of half of the 2048Mi memory limit, and the querier admits no more concurrent queries than the ten outstanding searches.

#### Scenario: The concurrent trace reads are bounded
- **WHEN** I run `uv run devops ci --check --only k8s` on values whose querier admits four concurrent queries and whose trace size cut is one million bytes
- **THEN** The row passes, because four concurrent queries hold at most four traces of one million bytes, 4000000 bytes, under the 1073741824 bytes of half of the memory limit.

#### Scenario: A limit above the memory bound fails the row
- **WHEN** I run `uv run devops ci --check --only k8s` after an edit lets the outstanding searches hold more than half of the memory limit, admits more concurrent queries than the outstanding-search limit, removes the trace size cut, or changes the memory limit
- **THEN** The row fails and names `k8s/otel/tempo-values.yaml`.
