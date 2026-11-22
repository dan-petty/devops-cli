## MODIFIED Requirements

### Requirement: The Tempo query limits stay under the memory limit
The Tempo configuration that chart `tempo` renders from `k8s/otel/tempo-values.yaml` SHALL set `query_frontend.max_outstanding_per_tenant`, `query_frontend.search.max_result_limit`, `query_frontend.api_timeout`, `querier.max_concurrent_queries` and `overrides.defaults.global.max_bytes_per_trace`. The searches and the concurrent reads that these limits admit SHALL hold at most half of the memory limit of the rendered `tempo` container.

#### Scenario: The Tempo values hold each limit
- **WHEN** I run `uv run devops ci --check --only k8s`
- **THEN** The row passes, and it fails when the rendered Tempo configuration does not set one of the five keys that this requirement names, or the rendered `tempo` container has no memory limit.

#### Scenario: An edited limit fails the row
- **WHEN** I run `uv run devops ci --check --only k8s` after an edit sets `tempo.queryFrontend.max_outstanding_per_tenant` to `50`
- **THEN** The row fails, because 50 outstanding queries of 50 results of `1000000` bytes are more than half of the memory limit, and it names `query_frontend.max_outstanding_per_tenant`.

#### Scenario: The outstanding searches fit under half of the memory limit
- **WHEN** I run `uv run devops ci --check --only k8s`
- **THEN** The row passes, because 10 outstanding queries of 50 results of `1000000` bytes are 500000000 bytes, under the 1073741824 bytes of half of the `2048Mi` limit.

#### Scenario: The concurrent trace reads are bounded
- **WHEN** I run `uv run devops ci --check --only k8s`
- **THEN** The row passes, because `querier.max_concurrent_queries` is `4`, no more than the `10` outstanding queries, and 4 concurrent queries of `1000000` bytes are 4000000 bytes, under half of the `2048Mi` limit; it fails when the querier admits more concurrent queries than the outstanding-query limit.

#### Scenario: A limit that the chart does not render fails the row
- **WHEN** I run `uv run devops ci --check --only k8s` after an edit puts the trace size limit under `tempo.global_overrides`, which the chart does not render
- **THEN** The row fails and names `overrides.defaults.global.max_bytes_per_trace` of the rendered Tempo configuration.

## ADDED Requirements

### Requirement: The rendered Tempo configuration parses with the Tempo image of the chart
The `k8s` row of `devops ci` SHALL render the chart source of the Argo CD Application `tempo` (`k8s/argocd/apps/tempo.yaml`) with `helm template`, and SHALL start the image of the rendered `tempo` container with the arguments of that container, `-config.verify=true`, no network and the rendered ConfigMaps at their mount paths. The row SHALL fail when Tempo exits with a status other than 0, and SHALL name the output of Tempo.

#### Scenario: The rendered configuration parses
- **WHEN** I run `uv run devops ci --check --only k8s`
- **THEN** The row passes, because the Tempo image of the chart parses the rendered `/conf/tempo.yaml` and exits 0.

#### Scenario: A key that the pinned Tempo does not have fails the row
- **WHEN** I run `uv run devops ci --check --only k8s` after an edit sets `tempo.queryFrontend.search.max_bytes_per_trace`
- **THEN** The row fails and shows `field max_bytes_per_trace not found in type frontend.SearchConfig`.
