# Design

## Context

The Service runs one worker for each lane of each repository in one process. They share the one GitHub session (`get_github_session`) and the one tracer. The session stores GET answers in an `LRUCache` for its next conditional GET. The tracer sends each payload to two export threads.

## Decisions

- **The session store is bounded by bytes and by count.** `LRUCache(maxsize=DEFAULT_GH_SESSION_ETAG_CACHE_BYTES, getsizeof=<size of one stored answer>)`, with the count bound kept. The size of an answer is the length of its text or bytes body, or of its encoded JSON for a decoded value. The size is counted once, when the answer is stored. An answer above the whole budget is returned and not stored, because `LRUCache` raises `ValueError` for it. The default budget is 64 MiB, a quarter of the memory request of the container.
- **The export queue is capped with a semaphore.** `_send_payload` takes a slot before it submits a payload, and the done callback of the future gives it back. When no slot is free, the payload is dropped and `export_dropped` grows by one. A drop is a counter and a debug log line, and it is no error, because telemetry must not stop a command.
- **The alert reads cAdvisor and kube-state-metrics.** The expression is the one of the issue. It divides the working set by the limit for the container `service` of the pods of the roadmap Service, and it waits 10 minutes.
- **The test measures the heap with `MemoryProfiler`.** It compares the heap after round 10 with the heap after round 200 and names the allocation sites that grew.

## Rejected Alternatives

- **Raise the memory limit.** A rise of 100 to 150 MiB each hour reaches any limit. Rejected by the issue and by measure 1: the store has no bound by bytes.
- **Set `MALLOC_ARENA_MAX=2` in the Deployment.** Measure 4 kept the resident set flat with no setting, and it was higher with the setting. The change adds it only if a later measure of the pod shows fragmentation.
- **Drop the oldest payload when the export queue is full.** `ThreadPoolExecutor` has no API to remove a queued item, so this needs a home-grown queue. Dropping the newest payload needs one semaphore.
- **`pytest-memray`.** It bounds the peak of a test and does not compare two rounds.
