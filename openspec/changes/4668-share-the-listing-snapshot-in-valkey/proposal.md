# Proposal: #4668

## Why

#4668 shares the listing snapshot of #4552 and the tool facts of the alternatives check in the cache Valkey `valkey-devops`, behind the circuit breaker of the cache tier. ADR 0023 section 2 sets the two tiers, and tracker #4624 lists the item as child 7.

- Each process that reads the listing with no local snapshot reads the full listing: 66 pages of 100 for the 6,571 issues and pull requests of devops-cli. The intake pods of #4567 start with an empty home, so each pod pays this read. A shared snapshot gives a cold process the newest copy, and the process then reads only the changes since its watermark.
- `_read_pypi` (`src/devops_cli/roadmap/alternatives.py:298`) opens a new HTTP client for each read and keeps no answer. `_linked_packages` (`src/devops_cli/roadmap/inventory.py:186`) does the same for deps.dev. The same tools come back on many items, and each release of the Service starts a new process with no fact in memory.

## What Changes

- `src/devops_cli/valkey/client.py`: `ValkeyClient` gets the hash commands `hget`, `hset`, `hdel` and `hscan`, and `expire`, `unlink` and `rename`. A read of a binary value uses the `NEVER_DECODE` option of valkey-py, so a zlib value comes back as bytes. A new method `watch_and_write` runs one WATCH, a check of the current value, and one MULTI/EXEC, and it says when another client changed the key first. It does not retry.
- `src/devops_cli/valkey/cache.py`: `ValkeyCacheTier` gets the same commands behind its circuit breaker. A command that fails, or that the open breaker does not send, is a miss or a skipped write, and the tier counts it in `devops_cli_valkey_cache_errors_total`.
- `src/devops_cli/valkey/tiered.py` (new): `TieredMapping`, a `MutableMapping` over an in-process `cachetools.TTLCache` and the shared `ValkeyCacheTier`. It has a key prefix, a JSON value with the schema key of its pydantic `TypeAdapter` in front, a TTL for each key, a bound of 1 MiB for each value, and the read and write counters. A read from the shared tier fills the in-process tier. A value of another schema is a miss.
- `src/devops_cli/roadmap/stores/listing_shared.py` (new): `ValkeySnapshotStore` and `TieredSnapshotStore` behind the `SnapshotStore` protocol. The snapshot of a repository is one hash, `valkey:roadmap:v1:snapshot:<owner>/<name>`, with the field `meta` and one zlib JSON `IssueRecord` for each issue, and a TTL of 7 days. A load reads the hash with `HSCAN COUNT 500` within a budget of 20 s. A writer writes only when its watermark is not older than the stored one, in one WATCH and MULTI/EXEC. A full read writes a temporary key and RENAMEs it. The store uses the shared copy and writes a key only for a public repository.
- `src/devops_cli/roadmap/stores/listing_snapshot.py`: `intake_listing` and `lane_listing` give `IncrementalListing` a `TieredSnapshotStore` over the `FileSnapshotStore` of today and the shared tier of the process. The callers of the two factories do not change.
- `src/devops_cli/roadmap/alternatives.py` and `src/devops_cli/roadmap/inventory.py`: the PyPI and deps.dev reads go through one fact `TieredMapping`, `valkey:brain:v1:fact:<source>:<name>`, with a TTL of 24 hours. A miss reads the source.
- `src/devops_cli/telemetry/instruments.py`: four counters with bounded labels: `devops_cli_brain_reads_total{store,result}`, `devops_cli_brain_writes_total{store,result}`, `devops_cli_valkey_cache_errors_total{op,error}` and `devops_cli_brain_github_requests_saved_total{store}`.
- `src/devops_cli/config/defaults.py` and `src/devops_cli/config/constants.py`: the TTLs, the load budget, the value bound, the HSCAN count, the size of the in-process tier, the key prefixes and the label values.
- `k8s/llm/valkey-devops.yaml`: `--maxmemory 256mb` in place of `96mb`, and a container limit of `384Mi` in place of `128Mi`. 256 MiB is two thirds of 384Mi, so the rule of `openspec/specs/llm-valkey/spec.md` (at most three quarters of the limit) holds, and so does the owner decision 6 of #4624 (256 MB).
- The contract suite of #4557 gets scenarios for WATCH with a lost transaction, `HSCAN` of binary values, `RENAME` of a hash with a TTL, `EXPIRE` and `UNLINK`, recorded from a real `valkey-server` of the image of `valkey-devops`.
- Documents: `k8s/README.md` (the memory bound and the new keys of `valkey-devops`), `docs/roadmap/intake.md` (the shared copy of the snapshot), `docs/roadmap/alternatives.md` (the fact cache) and the generated `docs/TELEMETRY.md`.
- The change adds service behavior that a consumer observes (the keys, the counters, the fallback and the memory bound), so it has a spec delta: the new nested capability `project-brain/shared-cache`, as ADR 0023 requires for each item of #4624.
- The change fits one pull request.

Out of scope, with the reason:

- The search and page caches that the body lists: the searches go to SearXNG and the pages to Crawl4AI, which run in the cluster and count no request against a quota. #4672 says that SearXNG carries the check and that Firecrawl answered 0 searches in 7 days.
- The GitHub answers (the SBOM of the inventory, the ADR index, the repository facts): ADR 0023 section 2 keeps the stored GitHub answers in the process. The conditional item of #4624 ("share stored GitHub answers through Valkey") holds them until the two-token probe of ADR 0021 section 6 passes.
- The live drill (`valkey-devops` at 0 replicas for 10 minutes) needs the merged code in the cluster. It is a check for a person after the release.

## Capabilities

### New Capabilities

- `project-brain/shared-cache`: the shared tier of the listing snapshot and the tool facts in `valkey-devops`: the read path, the fallback, the newest watermark, the value bound and the TTL, the key kinds, the private repositories, the load budget, the counters and the memory bound.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/valkey/client.py`, `src/devops_cli/valkey/cache.py`, `src/devops_cli/valkey/tiered.py`, `src/devops_cli/roadmap/stores/listing_shared.py`, `src/devops_cli/roadmap/stores/listing_snapshot.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/inventory.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`
- Manifests: `k8s/llm/valkey-devops.yaml`
- Documents: `k8s/README.md`, `docs/roadmap/intake.md`, `docs/roadmap/alternatives.md`, `docs/TELEMETRY.md`
- Tests: `tests/valkey/test_tiered.py`, `tests/valkey/test_valkey_cache_tier.py`, `tests/valkey/test_valkey_contract.py`, `tests/support/valkey_scenarios.py`, `tests/fixtures/valkey/recorded_exchanges.json`, `tests/support/fakes/valkey.py`, `tests/roadmap/stores/test_listing_shared.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_alternatives_project_facts.py`, `tests/conftest.py`
- Runtime: about 15 MB more data in `valkey-devops` for the public repositories, and 256 MiB more memory limit for its container. A workstation with no reachable Valkey makes one connection attempt of at most 0.25 s for each cooldown of 60 s.

## Feasibility

Each premise was checked on 2026-11-21 against `origin/main` at ddad1a45e and the live systems:

- The seam exists: `git grep -n "class SnapshotStore" origin/main -- src` gives `src/devops_cli/roadmap/stores/listing_snapshot.py:88`, with `FileSnapshotStore` at `:102` and `IncrementalListing` at `:161`. `IncrementalListing` calls only `load` and `save`.
- `ValkeyCacheTier` exists at `src/devops_cli/valkey/cache.py:70`. It offers `get` and `set` only, behind pybreaker (`fail_max=1`, a cooldown of 60 s, `ValkeyCommandError` excluded). `shared_cache_tier()` gives one tier for each process with a connect timeout of 0.25 s and the command timeout `valkey.timeout` (2 s, `src/devops_cli/config/defaults.py:723`).
- `ValkeyClient` builds its pool with `decode_responses=True` and `encoding_errors="replace"` (`src/devops_cli/valkey/client.py:196`), which would spoil a zlib value. valkey-py 6.2.0 has the per-command option `NEVER_DECODE` (`valkey/client.py:58`). A probe through fakeredis 2.40.0 gave `HSCAN k 0 COUNT 500` with `NEVER_DECODE` as `[b'0', [b'f', b'x\x9c...']]`, and `zlib.decompress` read the value back.
- #3670 and #4557 are closed as completed. #4552 is closed. #4704 (role ACL users of `valkey-devops`) is open.
- `_read_pypi` still opens `http_client(EgressLevel.PUBLIC)` for each read (`src/devops_cli/roadmap/alternatives.py:302`).
- No pull request names 4668 (`search/issues?q=repo:dan-petty/devops-cli+is:pr+4668` gives none), and no Job of the `devops` namespace names 4668.
- Visibility: `repos/dan-petty/devops-cli` gives `private=false`. Of the 8 repositories of `service.repos` in the live ConfigMap `devops-cli-config`, `homelab` and `danielpetty.com` are private. The other 6 are public. So the shared snapshot applies to devops-cli, and the store keeps the 2 private repositories in the local tier.
- The size of the snapshot, measured in the body on 2026-11-11: 4,615 records, 23.31 MB raw and 9.21 MB with zlib, p99 28,340 B and max 65,177 B for one record. Measured again on 2026-11-21 from the local snapshot of devops-cli (full read at 2026-11-20T22:13Z): 6,571 records, 37.54 MB raw, 14.13 MB with zlib for each record apart, p99 29,598 B and max 65,177 B raw, and max 23,700 B with zlib. Each record is far under the bound of 1 MiB, and the whole snapshot is over it, so the snapshot needs one field for each record.
- The memory of `valkey-devops`, from the owner comment of 2026-11-19: `redis_config_maxmemory{job="valkey-devops"}` is 100,663,296 (96 MiB). The old pod peaked at 95.97 MiB and evicted 3,600 keys in 7 days, with a hit ratio of 98.9 %. The new pod held 40.9 MiB in 2,871 keys with 0 evictions. The live Deployment runs `valkey/valkey:9.1.4-alpine` with a 128Mi limit. The snapshots of the 6 public repositories add about 15 MB, so 256 MiB keeps the embeddings, the snapshots and the facts with room to spare.
- The value of the shared snapshot comes with #4567, which is open. Today the Service runs intake in its own pod and keeps the snapshots on the volume `roadmap-service-home`, a PersistentVolumeClaim (`k8s/devops/roadmap-service/deployment.yaml:210`), so its rounds already read only the changes. The intake pods of #4567 start with no snapshot. The fact caches give value at once: the Service restarts at each release, and each restart empties the memory of the process.
- The load time of the shared devops-cli snapshot, measured on 2026-11-21 against a temporary Valkey pod `valkey-snapshot-load` of `valkey/valkey:9.1.4-alpine` (`--maxmemory 256mb`, limit `384Mi`) through a loopback port-forward from the devcontainer, never against the live `valkey-devops`: the 6,571 records of the local snapshot took 3.09 s to write and 15,714,823 bytes in Valkey (`MEMORY USAGE`). Five cold loads through `ValkeySnapshotStore` took 1.89, 1.56, 1.51, 2.14 and 2.61 s: a median of 1.89 s and a maximum of 2.61 s, under the budget of 20 s. The script is `.data/agent/scratch/4668/measure_load.py`, which is not in git.

## Existing Tool Considered

- valkey-py 6.2.0 (in `uv.lock`) gives the client, the hash commands, `NEVER_DECODE` and the WATCH pipeline. pybreaker 1.4.1 gives the circuit breaker, which `ValkeyCacheTier` already wraps. cachetools 8.0.2 gives the in-process `TTLCache` and the `cached` decorator, which accepts any `MutableMapping` as its cache. The change uses each of them and adds no dependency.
- The `SnapshotStore` protocol of #4552 is the seam: the two new stores implement it, and `IncrementalListing` and its callers do not change.
- No tool gives a mapping over an LRU and a Valkey tier with a breaker, a schema check and a value bound, or a snapshot store with a watermark guard. hishel is rejected: it is a shared cache by default, and the GitHub answers are private with `Vary: Authorization`. Page ETags are rejected for the listing: each new issue changes the ETag of every page (#4552).
- The change builds about 450 lines of code (the mapping, the two stores and the tier commands) and about 600 lines of tests. Cost, from the body: about 220,000 tokens and 6 hours to build. It keeps about 5,000 tokens a month and about 30,000 tokens for each fix.
- Internal code that the change deletes: none. `FileSnapshotStore` stays as the local tier.
