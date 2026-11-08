# Proposal

## Why

The pod of the roadmap Service was OOMKilled at its 1 GiB memory limit after 2 h 39 min (#4116). Its working set rises 100 to 150 MiB each hour from 370 to 460 MiB. Two structures of the Service have a bound by count and none by bytes: the GitHub session keeps 64 GET answers, and the tracer queues export payloads with no cap. No alert warns before the kill, because `RoadmapServiceRestarted` fires after it.

## What Changes

- Bound the answers that the GitHub session stores by bytes, with `DEFAULT_GH_SESSION_ETAG_CACHE_BYTES`, beside the count of `DEFAULT_GH_SESSION_ETAG_CACHE_SIZE`. An answer larger than the whole budget is returned and not stored.
- Cap the payloads that wait for export in the tracer with `DEFAULT_OTEL_EXPORT_QUEUE_MAX_PAYLOADS`, drop the payloads past the cap and count them in `export_dropped`.
- Add the alert `RoadmapServiceMemoryNearLimit` to the `roadmap-service` group of `k8s/monitoring/prometheus-values.yaml`: the working set of container `service` above 85% of its memory limit for 10 minutes. Add its step to the Roadmap service section of `k8s/README.md` and to the Alerting table.
- Add `tests/server/test_service_memory.py`, which runs the status lane's round 200 times over the real worker, session and tracer with the fakes of GitHub and of the collector, and measures the heap with `MemoryProfiler`.
- Record the byte budget in `docs/adr/0006-github-session-requests-go-through-gidgethub.md`.
- The change adds no Settings key and removes, renames or tightens none. The two new bounds are constants in `src/devops_cli/config/defaults.py`, so the example ConfigMap and the live ConfigMap load as before.
- The change does not raise the memory limit and does not set `MALLOC_ARENA_MAX`: the measure below does not prove an allocator cause.
- The change carries a spec delta, because the session, the exporter and the alerts are observable behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `github-session-answers`: The byte budget of the answers the GitHub session stores

### Modified Capabilities

- `otlp-export`: The export queue is bounded and counts its drops
- `roadmap-service-alerts`: The memory alert

## Impact

- Code: `src/devops_cli/github/session_transport.py`, `src/devops_cli/telemetry/tracer.py`, `src/devops_cli/config/defaults.py`
- Manifests: `k8s/monitoring/prometheus-values.yaml`
- Documents: `k8s/README.md`, `docs/adr/0006-github-session-requests-go-through-gidgethub.md`
- Tests: `tests/server/test_service_memory.py`, `tests/github/test_github_session.py`, `tests/telemetry/test_export_queue.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`

## Feasibility

- Live pod, read only, 2026-11-08: `kubectl top` showed 666 MiB at 04:26Z and 675 MiB at 04:32Z for a pod that started at 04:09Z with no restart. `/proc/1/status` showed RssAnon 667 MiB and RssFile 35 MiB, and the cgroup `memory.stat` showed anon 656 MiB and file 11 MiB. So the growth is process heap, and not page cache or git clones.
- Code read: `src/devops_cli/github/session_transport.py` builds `LRUCache(maxsize=DEFAULT_GH_SESSION_ETAG_CACHE_SIZE)` (64 answers) and `src/devops_cli/telemetry/tracer.py` builds `ContextPropagatingThreadPoolExecutor(max_workers=2)` with no queue cap.
- Measure 1, the session store: `uv run devops ci test tests/server/test_service_memory.py` runs 200 rounds of `RepoWorker` over the real session and tracer, one 1 MiB diff answer of a new URL in each round. On the base tree the heap grew 56.1 MiB between round 10 and round 200, and `gidgethub/sansio.py:64` held 64.00 MB of the allocations: 64 stored answers. The store grows to 64 times the largest answer and has no byte bound. A real page of issues (`state=all`, 100 items) is 793 KB as text and 1.25 MB decoded by `tracemalloc`, so 64 pages are about 80 MB. A pull request diff has no size bound.
- Measure 2, the export queue: `tests/telemetry/test_export_queue.py` blocks the exporter and sends 1000 payloads. On the base tree the collector takes all 1000 once it answers, and the client has no drop counter. So the queue has no bound.
- Measure 3, the rest of a round: the same test with answers of 1 KiB and 1000 rounds grew the heap 10.6 MiB. The largest sites were the span buffer (`tracer.py`, 1000 spans, bounded by count), the fakes' request records and the metric series. No other structure grows with the number of rounds.
- Measure 4, the allocator: a scratch run of 21 threads that parse and drop 8 pages of 100 issues in each round (1000 rounds) kept the resident set flat at 54 to 60 MiB with no `MALLOC_ARENA_MAX`, and 80 to 109 MiB with `MALLOC_ARENA_MAX=2`. This does not show fragmentation, so the change sets no arena limit. The 42 mappings of 64 MiB in the live pod (268 MiB resident) fit glibc arenas, but they also fit the stored answers.
- Open point: the two bounded structures give a plateau, and a plateau of 80 MB cannot alone explain a rise from 370 to 860 MiB. The size of the answers in the live pod is not measured. The fifth acceptance criterion of the issue (a flat working set over 6 hours) is read in Grafana after the roll out, and the pull request comment records it. If the working set still rises, the next step is a heap profile of the pod, and not a higher limit.
- Rollout: the change adds no Settings key. No key that the example ConfigMap or the live ConfigMap names changes. `tests/config` already loads the example ConfigMap into Settings, and group 4 runs it again.
- First checks: `uv run devops ci test tests/server/test_service_memory.py tests/github/test_github_session.py tests/telemetry/test_export_queue.py tests/prometheus/test_k8s_monitoring_alerting.py`, and `uv run devops ci fail-to-pass --base origin/main`.

## Existing Tool Considered

`cachetools` is already a dependency. Its `LRUCache` takes `getsizeof` with a `maxsize` in bytes, and it raises `ValueError` for one entry larger than `maxsize`, so the session uses it and adds the guard for an oversized answer. `tracemalloc` and `MemoryProfiler` measure the heap, and the change adds no new library. `concurrent.futures.ThreadPoolExecutor` has no queue cap, so the tracer counts the payloads that wait with a semaphore of the standard library. kube-state-metrics and cAdvisor already give `kube_pod_container_resource_limits` and `container_memory_working_set_bytes`, and the chart keeps both. `pytest-memray` was compared and rejected: it bounds the peak of one test, and it does not compare the heap at two rounds. The change deletes no internal code.

## Dependencies

None.
