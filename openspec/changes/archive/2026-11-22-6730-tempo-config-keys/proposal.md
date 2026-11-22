# Proposal: #6730

## Why

Pod `otel/tempo-0` (`docker.io/grafana/tempo:3.1.1`) stops at start, so the cluster stores no new traces (#6730). Its log: `failed parsing config: failed to parse configFile /conf/tempo.yaml: yaml: unmarshal errors: line 47: field max_bytes_per_trace not found in type frontend.SearchConfig; line 50: field target_bytes_per_second not found in type frontend.SearchConfig`. The limits of #6616 put two keys in the search block of the query frontend, and Tempo 3.1.1 has no such keys there. The trace size limit of #6616 went under `tempo.global_overrides`, which chart `tempo` 3.2.1 does not render, so Tempo never got it. No check rendered the chart and parsed the result with the Tempo binary that the chart runs.

## What Changes

- `k8s/otel/tempo-values.yaml` puts each limit of #6616 under the key that Tempo 3.1.1 reads, and keeps the aim of #6616: a search does not take Tempo over its `2048Mi` memory limit.
  - Remove `queryFrontend.search.max_bytes_per_trace`. Tempo 3.1.1 reads the trace size limit of a search from `overrides.defaults.global.max_bytes_per_trace`.
  - Move `global_overrides.max_bytes_per_trace: 1000000` to `overrides.defaults.global.max_bytes_per_trace: 1000000`. The chart renders `tempo.overrides` into the `overrides` block of the Tempo configuration.
  - Remove `queryFrontend.search.target_bytes_per_second`. Tempo 3.1.1 has no limit on the byte rate of a search.
  - Replace `queryFrontend.search.max_duration: 30s` with `queryFrontend.api_timeout: 30s`. In Tempo 3.1.1, `max_duration` is the largest time range of a search, so `30s` refuses each search of the last hour. #6616 meant the time that a read runs, and `api_timeout` is the key of that limit.
  - Keep `queryFrontend.search.max_result_limit: 50`, `queryFrontend.max_outstanding_per_tenant: 10`, `querier.max_concurrent_queries: 4` and the `2048Mi` memory limit.
- A new row `charts` of `devops ci` runs the checks of the chart sources of the Argo CD Applications (`tests/gate/charts.py`, `tests/gate/charts_checks/`). These checks start `helm` and `docker` and need the network, so they are not in the `k8s` row, which needs only `kubectl` and the files of the checkout. The implement Job runs `uv run devops ci --check --only k8s` when a plan names it as a verification command, and a Job pod has no container engine.
- `tests/gate/charts_render.py` holds `chart_objects`: it renders the chart source of an Argo CD Application with `helm template`, as `devops k8s image-pins` does, once for each run of the `charts` row.
- The new check `tests/gate/charts_checks/tempo_config.py` writes the rendered ConfigMap of Tempo to a folder and starts the Tempo image of the rendered StatefulSet with the arguments of its container and `-config.verify=true`. Tempo then parses the configuration strictly, checks it, and stops. The check fails when Tempo exits with a status other than 0.
- `tests/gate/charts_checks/tempo_query_limits.py` (moved from `tests/gate/k8s_checks/`) reads the rendered Tempo configuration and the rendered memory limit, not the values file. So a key that the chart does not render fails the check. It asserts the bounds of #6616 and no value: the outstanding searches times the result limit times the trace size limit, and the concurrent queries times the trace size limit, stay at or under half of the memory limit, and the concurrent queries are no more than the outstanding queries (docs/TESTING.md, #6060).
- `NOT_IN_RUNNER` of `src/devops_cli/roadmap/runner_tools.py` gives `helm` and `docker` a reason that stays true: only the `charts` row runs them, the Static Analysis job runs that row, and a Job cannot run it, so no verification command of a plan names it.
- The change modifies the requirement "The Tempo query limits stay under the memory limit" of `workload-resource-limits` and adds a requirement for the parse of the rendered configuration, because a manifest is behavior that a consumer observes. It adds the requirement of the `charts` row to `ci-gate-rows`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `workload-resource-limits`: The Tempo query limits stay under the memory limit; the rendered Tempo configuration parses with the Tempo image of the chart.
- `ci-gate-rows`: The `charts` row renders the chart sources of the Argo CD Applications, and the `k8s` row needs only `kubectl`.

## Impact

- Manifests: `k8s/otel/tempo-values.yaml`.
- Gate: `tests/gate/charts.py` (new), `tests/gate/charts_render.py` (new), `tests/gate/charts_checks/tempo_config.py` (new), `tests/gate/charts_checks/tempo_query_limits.py` (moved from `tests/gate/k8s_checks/`).
- Code: `src/devops_cli/commands/ci.py` and `src/devops_cli/lang/en/messages.py` (the `charts` row and its title), `src/devops_cli/roadmap/runner_tools.py` (two reasons of `NOT_IN_RUNNER`).
- The `charts` row needs `helm`, a container engine with the `docker` command and access to the chart repository and the image registry. The `k8s` row needs no new program. A stock GitHub runner and the devcontainer have them. The first run pulls the Tempo image, which takes about 5 s.

## Feasibility

- `kubectl -n otel get pod tempo-0` gave the image `docker.io/grafana/tempo@sha256:64e2fbd56d9c2b3412a4b430a58ea59e91a670b1e75f920a0c702213ad145044` and 95 restarts. `skopeo inspect docker://docker.io/grafana/tempo:3.1.1` gave the same digest.
- `helm template tempo tempo --repo https://grafana-community.github.io/helm-charts --version 3.2.1 --namespace otel --skip-tests --values k8s/otel/tempo-values.yaml` on main renders `query_frontend.search` with `max_bytes_per_trace` and `target_bytes_per_second`, and `overrides` with `defaults: {}`: the chart dropped `global_overrides`. The chart README says: "`global_overrides` => `overrides` (this is where the defaults for every tenant is set)".
- With the image of that digest, `-config.file=/conf/tempo.yaml -config.verify=true` on the rendered config of main exits 1 with the error of the pod. The same run on the rendered config of this change exits 0 and prints no warning. A full start of the image with that config and a `tmpfs` at `/var/tempo` logs `msg="Starting Tempo" version="(version=v3.1.1, ...)" target=all` and `msg="Tempo started"`.
- grafana/tempo at tag `v3.1.1`, `modules/frontend/search_sharder.go`: `SearchSharderConfig` holds `concurrent_jobs`, `target_bytes_per_job`, `default_result_limit`, `max_result_limit`, `max_duration`, `query_backend_after`, `ingester_shards`, `most_recent_shards`, `default_spans_per_span_set` and `max_spans_per_span_set`. `SLOConfig` holds `duration_slo` and `throughput_bytes_slo`, which only set a metric. No key limits the bytes of a trace or the byte rate of a search there.
- `modules/frontend/search_sharder.go:104` refuses a search when `End-Start` is more than `max_duration`: "range specified by start and end exceeds". The configuration docs of `v3.1.1` say: "The maximum allowed time range for a search."
- `modules/frontend/config.go:33`: `APITimeout time.Duration yaml:"api_timeout,omitempty"`. The docs of `v3.1.1`: "Set a maximum timeout for all api queries at which point the frontend will cancel queued jobs and return cleanly."
- `modules/overrides/config.go:207`: `GlobalOverrides` holds `max_bytes_per_trace`, which "is enforced in the Ingester, Compactor, Querier (Search)". `Overrides` holds `global`, and `Config` holds `defaults`.
- `modules/frontend/v1/frontend.go:34` holds `max_outstanding_per_tenant`, and `modules/querier/config.go:21` holds `max_concurrent_queries`.
- `cmd/tempo/main.go` reads `-config.verify`, parses the file with `yaml.UnmarshalStrict`, runs `CheckConfig`, and exits 1 on a parse error or on a warning. It starts no module, so it needs no storage and no network. The flag takes a value: `-config.verify` alone exits 2 with "flag needs an argument".
- A probe with an unknown key under `overrides.defaults` exits 1 too: "unknown extension key", so the check also catches an unknown override.

## Existing Tool Considered

Grafana Tempo (grafana/tempo, AGPL-3.0, maintained), with its own `-config.verify` flag, is the validator: the check runs the Tempo image that the chart pins on the configuration that the chart renders. Helm (`helm template`) renders the chart, and the container engine of the host runs the image. The change writes no parser and no list of Tempo keys, and it deletes the exact-value asserts of `tempo_query_limits.py`.
