# Design

## Decisions

### 1. The visibility check gives three answers

`listing_shared.py` adds `class Visibility(StrEnum)` with `PUBLIC`, `PRIVATE` and `UNKNOWN`. `repository_visibility(repo, *, runner=None) -> Visibility` replaces `repository_is_public`: `isPrivate: false` gives `PUBLIC`, `isPrivate: true` gives `PRIVATE`, and a `DevOpsCLIError` gives `UNKNOWN` with one warning log line. `TieredSnapshotStore` replaces its field `is_public: Callable[[str], bool]` with `visibility: Callable[[str], Visibility] = repository_visibility`.

- `PUBLIC`: the load and the save use the shared copy, as before.
- `PRIVATE`: the load counts `BrainRead.PRIVATE` and gives the local copy. The save counts `BrainWrite.PRIVATE` and writes no key. When the shared tier holds a copy (`meta` was read), the store sends `UNLINK` and counts `BrainWrite.REMOVED`.
- `UNKNOWN`: the load counts `BrainRead.UNKNOWN` and gives the local copy. The save counts `BrainWrite.UNKNOWN` and writes nothing. The store sends no `HSCAN`, `HSET`, `HDEL`, `RENAME` or `EXPIRE` for the key, and sends `UNLINK` only for a stale copy (decision 2a). The read of `meta` before the check stays: the store reads the visibility only after Valkey answered, so a round with Valkey down sends no visibility read.

### 2. The answers live in a TLRUCache with two lifetimes

The visibility answers move from a `dict` with a hand-written age check to a `cachetools.TLRUCache` keyed by `RepoRef(repo).key`, whose time-to-use function gives `now + DEFAULT_BRAIN_VISIBILITY_FAILURE_TTL_SECONDS` (60 s) for `UNKNOWN` and `now + DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS` (1,800 s) for the other two. Its timer is the clock seam (`devops_cli.core.clock.monotonic`), so the `clock` fixture moves it. Its size is `DEFAULT_BRAIN_MEMORY_ENTRIES` (1,024): the Service reads 8 repositories, and the old dictionary had no bound. The lock stays, because a `TLRUCache` is not thread-safe. `reset_shared_snapshots` clears it.

The owner decision of 2026-11-21 (comment on the pull request of #4668) accepts up to 1 hour for a repository that becomes private. With decision 2a, the bound is two times `DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS`, so the value goes from 3,600 s to 1,800 s. A process then sends two visibility reads for each repository in each hour, in place of one.

Trade-off: before this change, a failed read removed the shared copy, so the copy of a repository that became private stayed at most 1 hour. An unknown answer that leaves each copy would keep the copy of a repository that became private for as long as the reads fail. A read that fails for good, such as `Could not resolve to a Repository` for a token that cannot see the repository, would keep it until its key expires (7 days). Decision 2a bounds that case.

### 2a. An unknown answer removes a stale shared copy

The coordinator decided this on 2026-11-21, in place of an owner answer on the pull request (owner rule: decide open design questions with the best-practice answer and report them). A save comes only after a public answer: each write, and the `EXPIRE` of an unchanged save, sets the TTL of the key to `DEFAULT_BRAIN_SNAPSHOT_TTL_SECONDS`. The age of the last save is `DEFAULT_BRAIN_SNAPSHOT_TTL_SECONDS` less the `PTTL` of the key. A repository that became private gets no save after the public answers of the processes expire, so the age of its last save grows from then. An unknown answer removes the copy and counts the existing `BrainWrite.REMOVED` when that age is more than `DEFAULT_BRAIN_VISIBILITY_TTL_SECONDS` (30 min). A fresher copy stays, and the process with the unknown answer does not use it. A key with no TTL (`PTTL` -1) and a key that went (`PTTL` -2, or no `meta`) give no age, and the store removes nothing.

`ValkeySnapshotStore.meta` reads `meta` and the `PTTL` of the key in one pipeline with no MULTI/EXEC, through the new `ValkeyCacheTier.hget_with_ttl` and `ValkeyClient.hget_with_ttl`, so a load and a save send no extra round trip. `HeldMeta` holds the `PTTL`. The client method builds the valkey-py pipeline itself, because `ValkeyClient.pipeline` sends no per-command option and the `HGET` needs `NEVER_DECODE` to give the bytes of `meta` that the WATCH read of a write compares. A failure counts with `op="hget"`, as the plain read did.

The removal is one Lua script, through the new `ValkeyCacheTier.unlink_if_expiring` and the existing `ValkeyClient.eval`: Valkey reads the `PTTL` again and sends `UNLINK` only when the copy is still stale. Valkey runs a script as one step, so a save between the read of `meta` and the removal, such as a save of a Service lane while the visibility read of a Job fails, sets the TTL again and keeps the copy. The check of the `PTTL` that the load read stays, so a fresh copy costs no script. A failure counts with `op="unlink"`, as a plain removal does. The contract record of Valkey 9.1.4 covers `EVAL` through the project client.

Thus a short failure, such as a GraphQL quota that is out until its reset, keeps a fresh copy, which is the reason for this change. A process keeps a public answer for at most 30 min, so the last save of a repository that became private comes at most 30 min after the change. Its copy goes at most 1 hour after the change, at the first run after that, and not after 7 days. That is the bound that the owner accepted, and the bound of the code before this change. The store matches no error text: a failure that goes on, of each kind, gives the same bound. `docs/roadmap/intake.md`, `k8s/README.md` and the requirements "An unknown answer removes a stale shared copy" and "A visibility answer is kept for its lifetime" give the bound.

### 3. Two new label values

`BrainRead.UNKNOWN = "unknown"` and `BrainWrite.UNKNOWN = "unknown"`. The label set stays bounded: each value comes from the enums, which `test_the_brain_counters_send_only_fixed_labels` reads. The documents that list the result values change in the same pull request: the descriptions of `BRAIN_READS_TOTAL` and `BRAIN_WRITES_TOTAL` in `src/devops_cli/telemetry/instruments.py`, the generated `docs/TELEMETRY.md`, the docstrings of `BrainRead` and `BrainWrite`, and the text of the shared tier in `docs/roadmap/intake.md`. Census: `git grep -n 'result="private"\|brain_reads_total\|brain_writes_total' -- ':!openspec/changes/archive'` gives these files and the shared-cache spec only; no file under `k8s/` queries the counters.

### 4. The known records use one entry for each repository

Each of the 5 uses of `self._seen` in `ValkeySnapshotStore` (`records`, `_known`, `_kept` and `remove`) uses `RepoRef(repo).key`, the casefolded name that `snapshot_key` uses. The `ListingSnapshot` that a load gives keeps the `repo` text of its caller.

### 5. A total bound on the expanded records of one load

`DEFAULT_BRAIN_SNAPSHOT_LOAD_MAX_BYTES: int = 134_217_728` (128 MiB) in `src/devops_cli/config/defaults.py`. `ValkeySnapshotStore` takes it as its field `load_max_bytes`, so a test builds a store with a lower bound and patches no module attribute (docs/TESTING.md). `_decompressed` adds the length of each expanded record to a sum and gives None, with one info log line that names the bound, when the sum passes the bound. The check runs after each record, so a load expands at most the bound and one record (1 MiB). `records` then gives None, and `TieredSnapshotStore.load` counts `BrainRead.FALLBACK` and gives the local copy, as for each other miss.

The writer applies the same bound. When the record JSON of a save passes `load_max_bytes` in total, `ValkeySnapshotStore.write` gives `BrainWrite.OVERSIZE`, writes nothing, and logs one info line that names the bound. Thus no writer of the store stores a copy that each new process scans in full, expands to the bound and drops, and a later save of the same records does not keep that copy alive with `EXPIRE`. The stored copy, when there is one, stays and gets no new TTL. A writer of this version stored it under the bound, so a load accepts it. The load bound stays, because a writer of an older version can write a copy past the bound, and the values of the shared tier are untrusted.

The value: the local devops-cli snapshot of 2026-11-21 holds 6,616 records with 37,927,266 bytes of JSON (36.2 MiB) and 14,256,837 bytes with zlib. The bound limits the expanded bytes, not the zlib bytes: the design of the issue sized 64 MiB against "about 14 MB", which is the zlib size. Four times the measure is 144.7 MiB. The coordinator brief names 128 MiB for a measure near 36 MB, which is the power of two nearest to four times the measure: 3.5 times today's snapshot, so the snapshot can grow to about 23,000 records of today's mean size before a load is a miss. The record JSON grew 4.06 MB in the last 7 days and 27.7 MB in the last 30 days (review measure of 2026-11-21), so the snapshot comes to the bound in about 105 to 166 days. Then each save counts `oversize`, and each process reads its local copy or the full listing. A change of the bound, or of the form of the shared copy, must come before that time.

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
- **Treat a GraphQL `NOT_FOUND` answer of the visibility read as private:** rejected. It needs a new class of gh failure in the GitHub error classifier, which every gh command shares, or a match of the error text. Decision 2a bounds each failure that goes on with no match of the error text.
- **Ask the owner to accept the 7-day window:** rejected. Decision 2a gives a bound of 1 hour from data that Valkey already keeps.
- **Keep 3,600 s for an answer and for the age of a save:** rejected. The bound is then about 2 hours, two times the 1 hour that the owner accepted, and only the owner can accept a longer window (AGENTS.md rule 5).
- **Put the time of the public answer in the TTL of the key:** rejected. It keeps 3,600 s for an answer, but each save must set a TTL from the age of its answer, and the older answer of one process can make shorter the TTL that a newer answer set, so a fresh copy can go.
- **WATCH, `PTTL` and `UNLINK` in MULTI/EXEC for the removal:** rejected. It needs a new client method with the `WatchError` handling of `watch_and_write`. The script is one call of the existing `ValkeyClient.eval`.
- **An unconditional `UNLINK` after the check of the held `PTTL`:** rejected. A save during the visibility read sets the TTL again, and the `UNLINK` then removes a fresh copy, so each cold load is a miss until the next full write.
- **A save time in `meta`:** rejected. `meta` has no save time, and an unchanged save sends only `EXPIRE`, so a time in `meta` would not move. The `PTTL` moves with each save.
- **Remove the shared copy when a save passes the total bound:** rejected. A copy that a writer of this version stored is under the bound, so a load still accepts it, and a removal costs each cold process a full listing read. A copy past the bound from an older writer gets no new TTL and expires.
- **64 MiB (the design of the issue):** rejected. It was sized against the zlib size. Against the 36.2 MiB of JSON, it leaves 1.8 times the snapshot.
- **256 MiB (four times the measure, rounded up):** rejected. The design of the issue rejected it because a few lanes that load at the same time come near 1 GiB of JSON, plus the parsed records, under the 3Gi limit of `roadmap-service`.
- **A read time in the stored fact:** rejected. It adds bytes to each value, changes the schema key of each fact type, and depends on the clocks of two processes. `PTTL` is the time that Valkey keeps, with no extra round trip.
- **Do not fill the in-process tier on a Valkey hit:** rejected. The requirement "A read of the shared tier fills the in-process tier" asks for the fill, and each read would send a command.
- **A MULTI/EXEC transaction for `GET` and `PTTL`:** rejected. A key that expires between the two replies of a plain pipeline gives `PTTL` -2, which the mapping handles by not filling the in-process tier. A transaction adds two commands for that edge only.
- **A new `op` label value for the pipeline:** rejected. The read is the same `get` of the mapping, and `test_the_brain_counters_send_only_fixed_labels` holds the `op` values of a fact read to `get` and `set`.
