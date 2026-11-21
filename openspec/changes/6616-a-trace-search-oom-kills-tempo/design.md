# Design

## Decisions

- **Set Tempo's own search, outstanding-query, querier concurrency and trace size limits in the chart values, and keep the `2048Mi` memory limit.**: Tempo caps the bytes of a trace that a search reads, the result count, the search duration, the byte rate, the outstanding queries per tenant, the concurrent querier queries and the bytes of a trace it receives; a higher memory limit bounds no read and spends node memory (#6616).
- **Put the limits under `tempo.queryFrontend`, `tempo.querier` and `tempo.global_overrides`, and override no `tempo.config`.**: git_show f209f6c8 removed this file's own `config:` override, which rendered `query_frontend` from `.Values.tempo.queryFrontend`, `querier` from `.Values.tempo.querier` and `overrides` from `.Values.tempo.global_overrides`, and the header of `k8s/otel/tempo-values.yaml` says the chart builds the Tempo config from these values; a full `config` override pins one Tempo version's layout (#1813).
- **Assert the exact value of each of the seven limits and of the `2048Mi` memory limit in the check of the `k8s` row.**: A check that only bounds a product passes when a value or the memory limit changes; an exact value makes each scenario of the spec delta assertable and fails the row on any edit of the file.
- **Read the memory limit with `parse_quantity` of the `kubernetes` client.**: `tests/gate/k8s_checks/runner.py:10:from kubernetes.utils.quantity import parse_quantity` already reads a Kubernetes quantity in the gate, and a hand-written `Mi` parse fails on a limit written as `2Gi`.
- **Cut the spans of a trace beyond `1000000` bytes as Tempo receives it with `tempo.global_overrides.max_bytes_per_trace`, and bound how many reads hold memory at once by `querier.max_concurrent_queries` of `4` with `10` outstanding queries per tenant.**: The cut applies when Tempo receives a trace, so a trace that the store already holds can be larger and stays available for the retention of `168h`; the concurrency limit is what bounds how many reads hold memory of the pod at once.
- **Compare the restart count of pod `tempo-0` before and after the reproduction, and expect no increase.**: The issue records "The restart count went to 2.", so a live check that expects `0` fails after the change; the criterion of the issue is that the count does not increase.
- **Keep `k8s/argocd/apps/tempo.yaml`, `k8s/README.md` and `src/devops_cli/commands/k8s/stack_lifecycle.py` unchanged.**: Each of the three names the values file of the `tempo` release and no limit, so the change leaves each of them true.
- **Keep the restricted security context, the local-path volume and the chart pin at `3.2.1`.**: `k8s/argocd/apps/tempo.yaml:13:targetRevision: 3.2.1` and the restricted context that #1627 set stay as they are, and the change alters no other field of the file.

## Rejected alternatives

- **Set only `max_bytes_per_trace` on the search path.**: It leaves the result count, the search duration, the byte rate and the concurrency unbounded, so ten reads can still exhaust the memory limit; the alternatives check of the issue records the same gap for the tool alone.
- **Add a proxy in front of Tempo that refuses a large read.**: It adds code to build and keep where Tempo ships the search limits, the trace size limit and the concurrency limit, and the alternatives check of the issue gives the verdict in-use for grafana/tempo.
- **Raise the memory limit above `2048Mi`.**: `k8s/otel/tempo-values.yaml:39:memory: 2048Mi` is the budget that the plan keeps, and a higher limit bounds no read.
- **Override the whole `tempo.config`.**: The header of `k8s/otel/tempo-values.yaml` says the chart builds the Tempo config from these values, and git_show f209f6c8 removed exactly such an override because it pinned one Tempo version's layout (#1813).
- **Patch a separate ConfigMap with the Tempo configuration.**: It adds a second source of Tempo configuration where the chart builds the configuration from its values.
- **Claim that the trace size limit bounds a read of a trace by id.**: The limit applies when Tempo receives a trace, and a trace that the store already holds stays available for `k8s/otel/tempo-values.yaml:32:retention: 168h`, so the plan bounds that read by the concurrency limit and names the residual instead.
- **Expect a restart count of `0` in the live check.**: The issue records "The restart count went to 2.", so the check takes the count before and after the reproduction and expects no increase.
- **Write a pytest module that asserts the values of the Helm file.**: `tests/gate/tree_checks/config_values.py:78:_SKIPPED_PARTS: Final[frozenset[str]] = frozenset({"support", "fixtures", "golden", "gate"})` exempts the gate, and the check of the `k8s` row is the validator of the file.
- **Parse the `Mi` suffix of the memory limit by hand.**: `tests/gate/k8s_checks/runner.py:10:from kubernetes.utils.quantity import parse_quantity` already reads a Kubernetes quantity in the gate, and a hand-written parse fails on a limit written as `2Gi`.

## Unchanged references

- `k8s/argocd/apps/tempo.yaml` (quoted target): It names the values file of the `tempo` Application and no limit, and the change alters no field of it.
- `k8s/README.md` (documentation): Its Tempo row names the release and its values file, not a query limit, so the row stays true.
- `src/devops_cli/commands/k8s/stack_lifecycle.py` (chart values path): It names `otel/tempo-values.yaml` as the values file of the `tempo` release, which the change keeps.

## Security

Nothing crosses a trust boundary: the change sets limits in the Helm values of the trace store and adds no host name, no address, no secret and no account. A person must confirm on the cluster that the rendered Tempo configuration shows the search limits, the `10` outstanding queries, the `4` concurrent queries and the trace size limit, and must take the restart count of pod `tempo-0` before and after the ten searches and the trace reads: a read that still stops the pod is a defect of this change. The check `check_the_tempo_query_limits_stay_under_the_memory_limit` fails when a limit or the `2048Mi` memory limit differs from its value, or when the outstanding searches or the concurrent reads could hold more than half of the memory limit, and `uv run devops ci --check --only k8s` fails with it.
