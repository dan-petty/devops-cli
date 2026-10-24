# Design

## Context

See proposal.md, Why and Feasibility. The cache Valkey holds Open WebUI's state and its websocket pub/sub, and no other workload connects to it. It keeps no data across a restart (`--save ""`, `--appendonly no`). The live data set is 1.44 MiB at its peak, under a 2048Mi container limit.

## Goals / Non-Goals

**Goals:**

- Bound the data of the cache Valkey below its container limit, with room for the fragmentation and Valkey's own overhead.
- At the bound, refuse writes and keep every key, as the run index does.
- Hold both llm Valkeys to their bound and policy in a test.

**Non-Goals:**

- A Checkov step in CI (Decision 3).
- A guard against a returning `:latest` tag (Decision 4).
- An alert on the memory use of the cache Valkey (tasks.md, Workflow follow-up).

## Decisions

### Decision 1: `noeviction`, not `volatile-lru`

- **Rationale**: Open WebUI is the only client (#1654). Its keys with a TTL are token revocations, sign-in rate-limit buckets, task markers and cleanup locks, and none of them is a disposable cache entry. Under `volatile-lru`, Valkey evicts the least recently used of these keys first. Nothing reads a revocation until its revoked token comes back, so a revocation is a likely first victim, and the signed-out token becomes valid again. Open WebUI's Redis guide names `noeviction` for a capped instance. With `noeviction`, Valkey refuses writes at the bound with an error and keeps every key, as the run index does.
- **Rejected alternative**: `volatile-lru`, as the issue proposed. The issue chose it to evict the TTL entries of the LiteLLM and Portkey caches before the persistent keys. Neither connects to this Valkey since #1654, so the only keys that it can evict are Open WebUI's security and coordination keys.
- **Rejected alternative**: `allkeys-lru`. It also evicts the session and usage pools, which breaks the websockets, and the issue rejects it for that reason.

### Decision 2: `--maxmemory 1536mb`, three quarters of the limit

- **Rationale**: Valkey counts its allocated bytes against `maxmemory`, not its resident memory. The allocator keeps the pages that Valkey frees, so the resident memory follows the peak. The live `allocator_frag_ratio` is about 1.2, so 1536 MiB of data is about 1850 MiB resident, and the 18 MiB of the idle process still fits under 2048 MiB. Valkey's `mb` and the Kubernetes `Mi` are both 1024 × 1024 bytes. The pod has no replica, no AOF and no RDB, so `mem_not_counted_for_evict` is 0 and no fork doubles the memory. Each pub/sub client can hold an output buffer of 32 MiB at most (`client-output-buffer-limit pubsub 32mb`), and Valkey counts it inside `used_memory`.
- **Rejected alternative**: 1638 MiB or 1843 MiB, the 80 % to 90 % that Valkey's administration guide gives as an example. At a fragmentation of 1.2 they are about 1966 MiB and 2212 MiB resident, at or above the 2048Mi limit.
- **Rejected alternative**: a larger container limit. The measured peak is 1.44 MiB, so no data shows a need for more memory.

### Decision 3: no Checkov step

- **Rationale**: Checkov 3.3.19 `CKV_K8S_14` fails on `k8s/devops/cronjob.yaml` and `k8s/devops/roadmap-service/deployment.yaml`. They name the service image with no tag by design, because Argo CD Image Updater writes the digest into the `devops` Application (k8s/README.md, Service Image Updates).
- **Rejected alternative**: `k8s/.checkov.yaml` with a `skip-path` for those two workloads and for the CoreDNS patch. That is compensating code that the issue did not ask for, and each new untagged workload would need another skip.

### Decision 4: the `:latest` guard moves to a follow-up issue

- **Rationale**: No workload image under `k8s/` has the tag `latest` now. kube-linter 0.8.3 is in `tools.lock`, but its default `latest-tag` check also blocks an untagged image. A custom check from the `latest-tag` template with `.*:(latest)$` alone flags `:latest` and leaves the untagged service image alone. That is a CI change of its own.

## Open WebUI keys with no TTL

Open WebUI keeps most of its keys with no TTL: the session, usage and model pools, the task index, the collaborative-note documents, the cached tool and terminal server lists and the base model cache. `auth:user:<id>:revoked_at` also has no TTL when the JWT expiry is not set. A key with no TTL is never an eviction candidate, so no policy but `allkeys-*` can free it. Each of these keys follows live state, such as connected sessions, running tasks and open notes, and Open WebUI deletes it when that state ends. A key can stay when Open WebUI stops before its cleanup runs, but each Valkey restart starts empty. With `noeviction`, such growth ends at the bound with write errors that a person can see, not with an out-of-memory kill.

## Risks / Trade-offs

- At the bound, Open WebUI gets write errors, for example at sign-in, until a person finds the cause. The existing `ValkeyCacheErrors` alert does not cover a refused write, so an alert on the memory use moves to a follow-up issue.
- The rollout restarts the pod, and Valkey starts empty, as at each restart. Open WebUI's websocket clients connect again, and revocations from before the restart are lost, as they are at each restart today.
