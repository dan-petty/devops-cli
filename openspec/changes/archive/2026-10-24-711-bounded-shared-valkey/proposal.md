# Proposal

## Why

Issue #711: the cache Valkey of the llm stack (`k8s/llm/valkey.yaml`) starts with no `--maxmemory` and no `--maxmemory-policy` under a 2048Mi container limit. Its data can grow until the kernel kills the container for memory. The run index (`k8s/llm/valkey-runs.yaml`) already sets `--maxmemory 512mb` and `--maxmemory-policy noeviction`, but no test holds either manifest to a bound.

## What Changes

- `k8s/llm/valkey.yaml` starts valkey-server with `--maxmemory 1536mb` and `--maxmemory-policy noeviction`. A manifest comment gives the basis of the number and of the policy.
- `tests/test_k8s_valkey_stack.py` holds both llm Valkeys to the flag pair, and holds each bound to at most three quarters of its container memory limit.
- `k8s/README.md` says what the bound is and why Valkey evicts no key.
- The policy is `noeviction`, not the `volatile-lru` of the issue. Open WebUI is the only client of the cache Valkey, and its keys with a TTL are token revocations, sign-in rate-limit counters, task markers and locks. Open WebUI's Redis guide names `noeviction` for a capped instance (design.md, Decision 1).
- The Checkov CI step of the issue is not built: `CKV_K8S_14` fails on the untagged service image, which is untagged by design (Feasibility).
- No image needs a pin: no workload image under `k8s/` has the tag `latest`.

A manifest is observable, so the change carries a spec delta, in the new capability `llm-valkey`.

This change fits in one pull request.

## Capabilities

### New Capabilities

- `llm-valkey`: the memory bound of each Valkey in the llm namespace, and what Valkey does at that bound.

### Modified Capabilities

None.

## Impact

- `k8s/llm/valkey.yaml`: the two flags and their comment. Argo CD syncs the change from `main`, and the pod restarts with an empty data set, as at each restart (`--save ""`, `--appendonly no`).
- `tests/test_k8s_valkey_stack.py`: the bound test, and the full command of the cache Valkey.
- `k8s/README.md`: the bound and the policy of the cache Valkey.

## Feasibility

I confirmed the premise against the real system on 2026-10-24, at `origin/main` bba1f5ce:

- `k8s/llm/valkey.yaml` runs `exec valkey-server /run/valkey/auth.conf --save "" --appendonly no --dir /data` with a 2048Mi memory limit and no `--maxmemory`. `k8s/llm/valkey-runs.yaml` sets `--maxmemory 512mb --maxmemory-policy noeviction` under a 768Mi limit.
- The live pod (read-only `valkey-cli INFO memory`, Valkey 9.1.2, jemalloc-5.3.0) reports `used_memory` 1476520 (1.41M), `used_memory_peak` 1505240 (1.44M), `used_memory_rss` 18.19M, `maxmemory` 0, `maxmemory_policy` noeviction, `allocator_frag_ratio` 1.21 to 1.23, and `mem_not_counted_for_evict`, `mem_replication_backlog` and `mem_aof_buffer` all 0. `INFO keyspace` gives `db0:keys=2,expires=2`: the two Open WebUI cleanup locks. Two clients subscribe to pub/sub channels.
- Open WebUI is the only client. `test_open_webui_is_the_only_workload_that_names_the_cache_valkey` holds that, and `valkey-perimeter` admits only the `open-webui` pods on 6379 (#1654). LiteLLM and Portkey do not connect, so the issue's statement that they write to this Valkey is out of date.
- Open WebUI v0.11.4 source (`backend/open_webui`) sets a TTL on `auth:token:<jti>:revoked` and `auth:user:<id>:revoked_at` (`utils/auth.py`), the cleanup locks (`socket/utils.py`), `tasks:<id>` (`tasks.py`, 300 s) and the sign-in rate-limit buckets (`utils/rate_limit.py`). It sets no TTL on `session_pool`, `usage_pool` and `models` (`socket/main.py`), `tasks` and `tasks:item:<id>` (`tasks.py`), `tasks:response_streams` (only its fields expire, by `HEXPIRE`), the `ydoc:documents:*` lists and sets (`socket/utils.py`), `tool_servers` and `terminal_servers` (`utils/tools.py`), and the base model cache (`utils/models.py`).
- Valkey 9.1.2 `src/evict.c` samples the `volatile-*` candidates from `db->expires` only, the keys with a key-level TTL.
- Open WebUI's Redis guide (`open-webui/docs`, `docs/tutorials/integrations/redis.md`, commit 416b3593 of 2026-10-16) says: "Use **`noeviction`** (the safe default)", and "If you must cap memory, set a `maxmemory` limit paired with **`noeviction`**". It says that `volatile-lru` "can still drop a revocation early".
- Valkey's administration guide (`valkey-doc`, `topics/admin.md`) says: "`maxmemory` should be set by calculating the overhead for Valkey, other than data, and the fragmentation overhead. So if you think you have 10 GB of free memory, set it to 8 or 9." `topics/memory-optimization.md` says to provision for the peak, because the allocator does not give freed pages back. `topics/lru-cache.md` and `valkey.conf` of 9.1.2 add a replication and AOF buffer outside the count only when replicas or AOF are on.
- Checkov: `uvx --from checkov==3.3.19 checkov -d k8s --framework kubernetes --check CKV_K8S_14` exits 1 with 16 passed and 3 failed: `coredns/deployment-patch.yaml`, `devops/roadmap-service/deployment.yaml` and `devops/cronjob.yaml`. The last two name `ghcr.io/dan-petty/devops-cli/service` with no tag. k8s/README.md, Service Image Updates, says: "Git names the image untagged, and that entry sets its tag and digest", where Argo CD Image Updater writes the entry into the `devops` Application. A `skip-path` for those workloads is compensating code, so the Checkov step and `k8s/.checkov.yaml` leave the scope of this change.
- `grep -rnE 'image:.*:latest' k8s/` finds no match. The only `:latest` text under `k8s/` is the `imageName` that Image Updater follows (`k8s/argocd/image-updater-values.yaml`) and the README text about it. #727 removed LightLLM, and #738 pinned Portkey.
- kube-linter 0.8.3, which `tools.lock` pins, has a default `latest-tag` check with the block list `.*:(latest)$`, `^[^:]*$` and `(.*/[^:]+)$`. `kube-linter lint k8s/devops/cronjob.yaml` reports `latest-tag` on the untagged service image. A guard against a returning `:latest` tag therefore needs a custom check with `.*:(latest)$` alone, which moves to a follow-up issue (tasks.md).

## Existing Tool Considered

Valkey's own `maxmemory` and `maxmemory-policy` settings give the bound, so the change builds nothing. The guard against a `:latest` tag uses kube-linter, which `tools.lock` already pins, in a follow-up issue. Checkov 3.3.19 was considered for that guard and rejected: its `CKV_K8S_14` fails on an untagged image, and the service image is untagged by design. The change deletes no internal code.
