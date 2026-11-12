# Proposal: #4939

## Why

Issue #4939: the SearXNG worker grows about 50 MiB a day and is never replaced. In 4 days its resident memory rose from 160 MiB to 364 MiB against the container limit of 384 Mi, and the container was OOM-killed on 2026-11-12 at 05:26 UTC. The limits came from a short measurement (122 MiB peak for 10 queries at once), not from a pod that runs for days.

## What Changes

- The Deployment sets `GRANIAN_WORKERS_MAX_RSS` to `512`: Granian replaces a worker whose memory passes 512 MiB.
- The memory request goes from 192 Mi to 256 Mi and the limit from 384 Mi to 1 Gi, so the main process, the resource tracker, a worker at 512 MiB and the new worker during a replacement fit.
- "The limits" in `k8s/README.md` gives the growth, the cap and the new values.
- The SearXNG invariant tests hold the variable and the new resources.

## Feasibility

- The pinned image (`searxng/searxng:2026.10.23-629368e40`) runs Granian 2.8.4. `granian --help` in the image lists `--workers-max-rss INTEGER RANGE  The maximum amount of memory (in MiB) a worker can consume before respawn [env var: GRANIAN_WORKERS_MAX_RSS]`.
- Prometheus (`container_memory_rss`, `container_memory_working_set_bytes`, `container_memory_cache`, 6-hour steps over 4 days) shows rss 160 to 364 MiB with the cache under 1 MiB, so the growth is process memory, not page cache.
- `ps` in the pod after the restart: the main process 31 MiB, the resource tracker 12 MiB, `searxng worker-1` 90 MiB.
- The node that runs the pod has 64 GiB allocatable with 13 % requested, and namespace `devops` has no ResourceQuota or LimitRange.

## Existing Tool Considered

- Granian's own worker replacement (`--workers-max-rss`) covers the need. No code is added.
- Cost: about 60,000 tokens and 1 hour to build; nothing to keep.

## Impact

- `k8s/devops/searxng/deployment.yaml`, `k8s/README.md`, `tests/invariants/test_k8s_searxng.py`, spec `searxng-service`. The change fits one pull request.
- A replacement drops the requests that the old worker holds at that moment; at the measured growth this happens about once a week.
