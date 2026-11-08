# Tasks

## 1. Bound the answers the GitHub session stores by bytes

Reads: `src/devops_cli/github/session_transport.py`, `src/devops_cli/config/defaults.py`, `tests/github/test_github_session.py`, `tests/server/test_service_memory.py`. Changes: `src/devops_cli/github/session_transport.py`, `src/devops_cli/config/defaults.py`.

- [x] 1.1 Add the tests `test_the_session_keeps_the_answers_of_its_latest_reads_within_the_byte_budget` and `test_an_answer_larger_than_the_byte_budget_is_returned_and_not_stored` to `tests/github/test_github_session.py`, and `tests/server/test_service_memory.py`. Run them and see them fail on the base
  - Verification: `$ uv run devops ci test tests/github/test_github_session.py tests/server/test_service_memory.py` fails on the base
- [x] 1.2 Add `DEFAULT_GH_SESSION_ETAG_CACHE_BYTES` (64 MiB) to `src/devops_cli/config/defaults.py` with a comment, and make the store of `SessionGitHubAPI` an `LRUCache` with `maxsize` in bytes and `getsizeof` for the size of a stored answer. Keep the count bound. Do not store an answer larger than the budget
  - Verification: `$ uv run devops ci test tests/github/test_github_session.py tests/server/test_service_memory.py` passes

## 2. Cap the export queue of the tracer

Reads: `src/devops_cli/telemetry/tracer.py`, `src/devops_cli/config/defaults.py`, `tests/telemetry/test_export_queue.py`. Changes: `src/devops_cli/telemetry/tracer.py`, `src/devops_cli/config/defaults.py`.

- [x] 2.1 Add `tests/telemetry/test_export_queue.py`. Run it and see it fail on the base
  - Verification: `$ uv run devops ci test tests/telemetry/test_export_queue.py` fails on the base
- [x] 2.2 Add `DEFAULT_OTEL_EXPORT_QUEUE_MAX_PAYLOADS` (256) to `src/devops_cli/config/defaults.py`. In `OTelTelemetryClient`, take a slot of a semaphore in `_send_payload` before the submit, give it back in the done callback, and count a payload without a free slot in `export_dropped`
  - Verification: `$ uv run devops ci test tests/telemetry/test_export_queue.py tests/telemetry/test_telemetry_shutdown_sync.py tests/telemetry/test_telemetry.py` passes

## 3. Warn before the memory limit

Reads: `k8s/monitoring/prometheus-values.yaml`, `k8s/README.md`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`. Changes: `k8s/monitoring/prometheus-values.yaml`, `k8s/README.md`.

- [x] 3.1 Update the expected rules in `tests/prometheus/test_k8s_monitoring_alerting.py` and add the promtool case to `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`. Run them and see them fail on the base
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base
- [x] 3.2 Add the rule `RoadmapServiceMemoryNearLimit` to the `roadmap-service` group after `RoadmapServiceRestarted`, its step in the Roadmap service section of `k8s/README.md` (read the working set with `kubectl -n devops top pod`, search the log for the first drop of a payload, then read the log) and its row in the Alerting table
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes

## 4. Documents and checks

Reads: `docs/adr/0006-github-session-requests-go-through-gidgethub.md`, `config.example.yaml`. Changes: `docs/adr/0006-github-session-requests-go-through-gidgethub.md`.

- [x] 4.1 Record in ADR 0006 that the session bounds its stored answers by bytes with `DEFAULT_GH_SESSION_ETAG_CACHE_BYTES` and by count, and that an answer above the budget is not stored
  - Verification: `$ git grep -n DEFAULT_GH_SESSION_ETAG_CACHE_BYTES docs/adr/0006-github-session-requests-go-through-gidgethub.md`
- [x] 4.2 Prove that the example ConfigMap and the settings still load, because the change adds and renames no key
  - Verification: `$ uv run devops ci docs`
- [x] 4.3 Run the memory tests together
  - Verification: `$ uv run devops ci test tests/server/test_service_memory.py tests/github/test_github_session.py tests/telemetry/test_export_queue.py`

## Workflow follow-up

- Pending a person: read `container_memory_working_set_bytes` of container `service` in Grafana after 6 hours of the new pod, and record it in the pull request comment (the fifth acceptance criterion of #4116).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
