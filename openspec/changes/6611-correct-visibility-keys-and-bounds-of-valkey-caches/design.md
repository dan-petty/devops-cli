# Design

## Decisions

### 1. The visibility check gives three answers

`listing_shared.py` adds `class Visibility(StrEnum)` with `PUBLIC`, `PRIVATE` and `UNKNOWN`. `repository_visibility(repo, *, runner=None) -> Visibility` replaces `repository_is_public`: `isPrivate: false` gives `PUBLIC`, `isPrivate: true` gives `PRIVATE`, and a `DevOpsCLIError` gives `UNKNOWN` with one warning log line. `TieredSnapshotStore` replaces its field `is_public: Callable[[str], bool]` with `visibility: Callable[[str], Visibility] = repository_visibility`.

- `PUBLIC`: the load and the save use the shared copy, as before.
- `PRIVATE`: the load counts `BrainRead.PRIVATE` and gives the local copy. The save counts `BrainWrite.PRIVATE` and writes no key. When the shared tier holds a copy (`meta` was read), the store sends `UNLINK` and counts `BrainWrite.REMOVED`.
- `UNKNOWN`: the load counts `BrainRead.UNKNOWN` and gives the local copy. The save counts `BrainWrite.UNKNOWN` and writes nothing. The store sends no `HSCAN`, `HSET`, `HDEL`, `RENAME`, `EXPIRE` or `UNLINK` for the key. The `HGET` of `meta` before the check stays: the store reads the visibility only after Valkey answered, so a round with Valkey down sends no visibility read.

### 2. The answers live in a TLRUCache with two lifetimes

The visibility answers move from a `dict` with a hand-written age check to a `cachetools.TLRUCache` keyed by `RepoRef(repo).key`, whose time-to-use function gives `now + DEFAULT_BRAIN_VISIBILITY_FAILURE_TTL_SECONDS` (60 s) for `UNKNOWN` and `now + DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS` (3,600 s) for the other two. Its timer is the clock seam (`devops_cli.core.clock.monotonic`), so the `clock` fixture moves it. Its size is `DEFAULT_BRAIN_MEMORY_ENTRIES` (1,024): the Service reads 8 repositories, and the old dictionary had no bound. The lock stays, because a `TLRUCache` is not thread-safe. `reset_shared_snapshots` clears it.

The owner decision of 2026-11-21 (comment on the pull request of #4668) accepts up to 1 hour for a repository that becomes private, so `DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS` stays 3,600 s.

### 3. Two new label values

`BrainRead.UNKNOWN = "unknown"` and `BrainWrite.UNKNOWN = "unknown"`. The label set stays bounded: each value comes from the enums, which `test_the_brain_counters_send_only_fixed_labels` reads. The documents that list the result values change in the same pull request: the descriptions of `BRAIN_READS_TOTAL` and `BRAIN_WRITES_TOTAL` in `src/devops_cli/telemetry/instruments.py`, the generated `docs/TELEMETRY.md`, the docstrings of `BrainRead` and `BrainWrite`, and the text of the shared tier in `docs/roadmap/intake.md`. Census: `git grep -n 'result="private"\|brain_reads_total\|brain_writes_total' -- ':!openspec/changes/archive'` gives these files and the shared-cache spec only; no file under `k8s/` queries the counters.

### 4. The known records use one entry for each repository

Each of the 5 uses of `self._seen` in `ValkeySnapshotStore` (`records`, `_known`, `_kept` and `remove`) uses `RepoRef(repo).key`, the casefolded name that `snapshot_key` uses. The `ListingSnapshot` that a load gives keeps the `repo` text of its caller.

### 5. A total bound on the expanded records of one load

`DEFAULT_BRAIN_SNAPSHOT_LOAD_MAX_BYTES: int = 134_217_728` (128 MiB) in `src/devops_cli/config/defaults.py`. `_decompressed` adds the length of each expanded record to a sum and gives None, with one info log line that names the bound, when the sum passes the bound. The check runs after each record, so a load expands at most the bound and one record (1 MiB). `records` then gives None, and `TieredSnapshotStore.load` counts `BrainRead.FALLBACK` and gives the local copy, as for each other miss.

The value: the local devops-cli snapshot of 2026-11-21 holds 6,616 records with 37,927,266 bytes of JSON (36.2 MiB) and 14,256,837 bytes with zlib. The bound limits the expanded bytes, not the zlib bytes: the design of the issue sized 64 MiB against "about 14 MB", which is the zlib size. Four times the measure is 144.7 MiB. The coordinator brief names 128 MiB for a measure near 36 MB, which is the power of two nearest to four times the measure: 3.5 times today's snapshot, so the snapshot can grow to about 23,000 records of today's mean size before a load is a miss.

Until #6614 (claimed for the next wave) adds one scan for each repository, each lane of the Service that starts at the same time scans the whole snapshot. #6614 limits the peak of lanes that load at the same time; this bound limits one load.

The module docstring of `listing_shared.py` gives the sizes as 38 MB of JSON and 14 MB with zlib, in place of "about 14 MB".

### 6. An in-process value expires with its Valkey key

`ValkeyCacheTier.get_with_ttl(key) -> tuple[str | None, int] | None` sends `GET` and `PTTL` through `ValkeyClient.pipeline` (one round trip, no MULTI/EXEC) behind the breaker, and gives None on a failure. It counts a failure with `op="get"`, so the `op` label set does not grow and the counters of a fact read keep their meaning.

The in-process tier of `TieredMapping` becomes `TLRUCache[str, _Held[V]]` of `DEFAULT_BRAIN_MEMORY_ENTRIES`, where `_Held` holds the value and its expiry time on the clock seam, and the time-to-use function gives that expiry. A write keeps the value for `ttl` seconds. A Valkey hit keeps it for the smaller of `ttl` and `PTTL / 1000` seconds. `PTTL` -1 (a key with no TTL, which no writer of the mapping makes) gives `ttl`. `PTTL` -2 (the key expired between the two commands) gives the value to the caller and does not fill the in-process tier. `__iter__` and `__len__` keep their behavior.

### 7. No live measurement

The tests assert each requirement offline on the `valkey_server` fake, the `clock` fixture, the `RecordedGh` runner and the OTLP fake. The pull request names no live check.

## Rejected alternatives

- **A `bool` with a sentinel for an unknown answer:** rejected. A sentinel mixes the unknown answer with a false value, and the removal of defect 1 comes from that mix.
- **An exception for an unknown answer:** rejected. The load and the save continue with the local tier, so an exception adds control flow to both and to each caller.
- **Count an unknown answer as `private` or `fallback`:** rejected. `private` hides a failed read behind a real answer, and `fallback` means that the shared tier is down. An operator must tell the three apart.
- **Keep a failed read until the reset time that the error gives:** rejected. The `DevOpsCLIError` of a failed `gh` GraphQL read carries the text of the error, not a reset time, and a failure that is not a quota failure (HTTP 502 in the existing tests) has none. A fixed 60 s needs no parse.
- **Keep no failed read:** rejected. The issue measured one more GraphQL request for each lane round while the quota is out.
- **A bound for each record only:** rejected. The issue measured a tracemalloc peak of 151 MiB for 150 fields of 1,040 bytes of zlib each.
- **64 MiB (the design of the issue):** rejected. It was sized against the zlib size. Against the 36.2 MiB of JSON, it leaves 1.8 times the snapshot.
- **256 MiB (four times the measure, rounded up):** rejected. The design of the issue rejected it because a few lanes that load at the same time come near 1 GiB of JSON, plus the parsed records, under the 3Gi limit of `roadmap-service`.
- **A read time in the stored fact:** rejected. It adds bytes to each value, changes the schema key of each fact type, and depends on the clocks of two processes. `PTTL` is the time that Valkey keeps, with no extra round trip.
- **Do not fill the in-process tier on a Valkey hit:** rejected. The requirement "A read of the shared tier fills the in-process tier" asks for the fill, and each read would send a command.
- **A MULTI/EXEC transaction for `GET` and `PTTL`:** rejected. A key that expires between the two replies of a plain pipeline gives `PTTL` -2, which the mapping handles by not filling the in-process tier. A transaction adds two commands for that edge only.
- **A new `op` label value for the pipeline:** rejected. The read is the same `get` of the mapping, and `test_the_brain_counters_send_only_fixed_labels` holds the `op` values of a fact read to `get` and `set`.
