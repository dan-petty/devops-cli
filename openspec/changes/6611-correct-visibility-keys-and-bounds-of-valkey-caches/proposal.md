# Proposal: #6611

## Why

#6611 corrects four defects of the shared listing snapshot and the fact caches of the project brain, which #4668 added. The second review of #4668 found them on `main` after the merge:

1. A failed visibility read removes the shared copy of a public repository. `repository_is_public` gives False on `DevOpsCLIError` and keeps no answer, and `TieredSnapshotStore._public` then sends `UNLINK` of the snapshot key. The visibility read uses GraphQL, whose quota runs out from time to time. While the read fails, each lane round sends one more GraphQL request, no process writes the copy again, and each cold pod reads the full listing.
2. `ValkeySnapshotStore._seen` is keyed by the text of the repository name, but the Valkey key and the visibility answers use `RepoRef(repo).key`. Two spellings of one repository in one process (a name from the config and the `full_name` of a webhook) share one key but have two entries, so each save in turn writes all records to a temporary key.
3. `_decompressed` limits each record to `DEFAULT_BRAIN_VALUE_MAX_BYTES` (1 MiB), but no limit applies to the sum. Many small zlib values that each expand to just under 1 MiB can take a load past the 3Gi memory limit of `roadmap-service`. The values of the shared tier are untrusted.
4. A Valkey hit puts a fact in the in-process tier with a full new TTL, so a long-lived process can give a PyPI or deps.dev fact up to about 48 hours after the source read. The documented bound is 24 hours (`DEFAULT_BRAIN_FACT_TTL_SECONDS`).

## What Changes

- The visibility check gives one of three answers, `Visibility.PUBLIC`, `PRIVATE` or `UNKNOWN`. `repository_visibility` replaces `repository_is_public`, and a failed read gives `UNKNOWN`. Only a private answer removes the shared copy. An unknown answer does not read the records of, write or remove the shared copy, and counts `result="unknown"` on `devops_cli_brain_reads_total` and `devops_cli_brain_writes_total`. A process keeps an unknown answer for `DEFAULT_BRAIN_VISIBILITY_FAILURE_TTL_SECONDS` (60 s) and a public or private answer for `DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS` (1 hour, kept by the owner decision of 2026-11-21), in a `cachetools.TLRUCache`. `TieredSnapshotStore` takes the check as its field `visibility`.
- `ValkeySnapshotStore._seen` uses `RepoRef(repo).key` in each read, write and removal, as `snapshot_key` does.
- A load of a shared snapshot expands at most `DEFAULT_BRAIN_SNAPSHOT_LOAD_MAX_BYTES` (128 MiB) of record JSON in total. A load past the bound is a miss and counts `result="fallback"`, as each other miss does. A save whose record JSON passes the bound writes no key and counts `result="oversize"`, so no writer stores a copy that no load accepts.
- The in-process tier of `TieredMapping` becomes a `cachetools.TLRUCache`. A Valkey hit reads the value and the remaining TTL of its key (`GET` and `PTTL`) in one round trip through the new `ValkeyCacheTier.get_with_ttl`, and the value leaves the in-process tier no later than the Valkey key.
- The change alters what a consumer observes (the keys in `valkey-devops`, the counters and the commands that the stores send), so it carries a spec delta.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-brain/shared-cache`: "No key of a private repository" (a failed read is unknown and leaves the shared copy), "A load counts the tier that gave the snapshot" (a private or unknown answer counts in place of `local`), "One key for each repository" (the known records of a process use one entry), "A read of the shared tier fills the in-process tier" (the value expires with its Valkey key), and the new requirements "A visibility answer is kept for its lifetime" and "A shared snapshot has a bound on its expanded records".

## Impact

- Code: `src/devops_cli/roadmap/stores/listing_shared.py`, `src/devops_cli/valkey/tiered.py`, `src/devops_cli/valkey/cache.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/telemetry/instruments.py`.
- Tests: `tests/roadmap/stores/test_listing_shared.py`, `tests/valkey/test_tiered.py`, `tests/valkey/test_valkey_cache_tier.py`.
- Documents: `docs/TELEMETRY.md` (generated), `docs/roadmap/intake.md`, `k8s/README.md` (the bound of a repository that became private).
- Metrics: the `result` label of `devops_cli_brain_reads_total` and `devops_cli_brain_writes_total` gets the value `unknown`. Each value still comes from a fixed enum. No dashboard or alert of the repository queries the two counters (`git grep -n "brain_reads\|brain_writes" k8s/` gives no line).
- Runtime: no new dependency, no new setting and no manifest change. While the GraphQL quota is out, a process sends at most one visibility read for each repository in each 60 s, and the shared copy stays.
- The change fits one pull request.

## Feasibility

Each premise was checked on 2026-11-21 against `origin/main` at c6395d856:

- Defect 1: `src/devops_cli/roadmap/stores/listing_shared.py:457` `repository_is_public` returns False in its `except DevOpsCLIError` branch (`:470`) before it stores the answer, and `TieredSnapshotStore._public` (`:555`) calls `shared.remove(repo)` (`:560`) for each answer that is not True.
- Defect 2: `grep -c "self._seen" src/devops_cli/roadmap/stores/listing_shared.py` gives 5 (lines 235, 258, 329, 388 and 394), each with the `repo` text as key, while `snapshot_key` (`:150`) and the visibility answers (`:462`) use `RepoRef(repo).key`.
- Defect 3: `_decompressed` (`:413`) passes `DEFAULT_BRAIN_VALUE_MAX_BYTES` to each `decompress` call and keeps no sum.
- Defect 4: `src/devops_cli/valkey/tiered.py:102` builds a `TTLCache(maxsize=entries, ttl=ttl)`, and the Valkey hit at `:129` puts the value in it with no read of the remaining TTL.
- No open pull request names 6611 (`search/issues?q=repo:dan-petty/devops-cli+is:pr+is:open+6611` gives 0), and no Job of the `devops` namespace names 6611.
- `uv run python -c "import cachetools, inspect; print(cachetools.__version__, inspect.signature(cachetools.TLRUCache.__init__))"` gives `8.0.2 (self, maxsize, ttu, timer=<built-in function monotonic>, getsizeof=None)`: the time-to-use function gives the expiry of each entry.
- A probe of fakeredis 2.40.0 through a raw valkey-py pipeline (`transaction=False`) gave `['v', 5000]` for `GET` and `PTTL` of a key set with `ex=5`, `[None, -2]` for a missing key, and no value after `time_machine` moved the clock 6 s. So a test asserts the expiry offline with the `clock` fixture. `ValkeyClient.pipeline` already sends commands in one round trip without MULTI/EXEC.
- The size of the devops-cli snapshot, measured on 2026-11-21 from the local snapshot file of the main checkout (read only): 6,616 records, 37,927,266 bytes of record JSON (36.2 MiB) and 14,256,837 bytes with zlib for each record (13.6 MiB). The largest record is 64,897 bytes of JSON.

## Existing Tool Considered

- cachetools 8.0.2 (in `uv.lock`, MIT, maintained; the alternatives check of the issue gives the verdict `in-use`) gives `TLRUCache`, an LRU cache with an expiry time for each entry. It replaces the `TTLCache` of `TieredMapping` and the hand-written time check of the visibility answers.
- valkey-py 6.2.0 (in `uv.lock`) gives the non-transactional pipeline that `ValkeyClient.pipeline` wraps, so `GET` and `PTTL` go in one round trip with no new client method.
- No tool gives a three-state visibility answer, a bound on the sum of expanded records, or the `RepoRef` key of the known records: they stay project code. The written cost of that code: about 150 lines of source and 250 lines of tests, about 60,000 tokens to build, 5,000 tokens a year to keep and 10,000 tokens to fix, and 1 day of elapsed time.
- Internal code that the change deletes: `repository_is_public` and its `bool` answer, the hand-written age check of the `_visibility` dictionary, and the `TTLCache` of `TieredMapping`.
