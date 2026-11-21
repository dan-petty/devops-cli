# Tasks

## 1. Cap the Tempo search limits and add the k8s check

Kind: other. Reads: `k8s/otel/tempo-values.yaml`, `tests/gate/k8s_checks/telemetry_resource.py`, `tests/gate/k8s_checks/otel_endpoints.py`, `tests/gate/runner.py`, `tests/support/paths.py`. Changes: `k8s/otel/tempo-values.yaml`, `tests/gate/k8s_checks/tempo_query_limits.py` (new).

- [ ] 1.1 Write the check in `tests/gate/k8s_checks/tempo_query_limits.py`, in the shape of `tests/gate/k8s_checks/telemetry_resource.py`: a module docstring, `import yaml`, `from tests.support.paths import REPO_ROOT`, and the constant `TEMPO_VALUES = REPO_ROOT / "k8s" / "otel" / "tempo-values.yaml"`. The function `check_the_tempo_query_limits_stay_under_the_memory_limit` loads `k8s/otel/tempo-values.yaml` with `yaml.safe_load`, reads `tempo.resources.limits.memory`, and parses its `Mi` suffix into bytes. It asserts the four values under `tempo.queryFrontend.search` and the two under `tempo.queryFrontend` and `tempo.querier`, the product `max_outstanding_per_tenant * max_result_limit * max_bytes_per_trace` at most half of the memory limit, and `querier.max_concurrent_queries` no more than `max_outstanding_per_tenant`, with a message that names the file and the key. On the base the check fails, because the keys are absent. Then add the `queryFrontend` and `querier` blocks under `tempo:` in `k8s/otel/tempo-values.yaml`, below `resources`, with a comment that names #6616 and the memory bound, and leave `securityContext`, `resources`, `persistence` and `affinity` as they are
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 2. Cut oversized traces at ingestion and assert the cut

Kind: other. Reads: `k8s/otel/tempo-values.yaml`, `tests/gate/k8s_checks/tempo_query_limits.py`. Changes: `k8s/otel/tempo-values.yaml`, `tests/gate/k8s_checks/tempo_query_limits.py`.

- [ ] 2.1 Add `global_overrides` with `max_bytes_per_trace: 1000000` under `tempo:` in `k8s/otel/tempo-values.yaml`, next to the query limits, with a comment that names #6616 and says that Tempo cuts a trace above that size when it is pushed, so every trace the store receives after the change is at most 1000000 bytes and the older, larger ones leave it within the retention of 168h. Extend `check_the_tempo_query_limits_stay_under_the_memory_limit` in `tests/gate/k8s_checks/tempo_query_limits.py` to require the key and to assert that `querier.max_concurrent_queries` times `global_overrides.max_bytes_per_trace` stays under half of the memory limit, with a message that names the file and the key. The check fails on the tree of group 1, where the key is absent
  - Verification: `$ uv run devops ci --check --only k8s` passes
