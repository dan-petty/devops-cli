# Design

## Decisions

The coordinator decided items 1 to 8 of the delivery brief on 2026-11-21 (owner rule: decide open design questions with the best-practice answer and report them). They replace the refine design of the issue where the two differ. The refine design was written before #6611 merged, so the line numbers below are those of `origin/main` at 3f8f7a90e.

### 1. A save decides before it encodes

`ValkeySnapshotStore.write(snapshot, held)` works in this order:

1. OLDER: when the stored `meta` parses, has the schema key of the snapshot and has a newer watermark than the snapshot, `write` gives `BrainWrite.OLDER` before it encodes a record. A stored copy with another schema key is never older. `may_replace` takes the schema key and the watermark, which the snapshot and `SharedMeta` both give, so the check needs no digest.
2. Known records: the store reads the `_seen` entry of `RepoRef(repo).key` under `self._lock`. It knows the stored records when the entry has its records and the digest of the entry is the digest of the stored `meta`.
3. Compare: with known records, each record of the snapshot is compared with the known record of the same number (`IssueRecord.__eq__`; the records are frozen). A record with no known record is new. A known number that is not in the snapshot is removed. Only the changed and new records are encoded to JSON and digested. The digests and JSON lengths of the equal records come from the entry. Without known records, every record is encoded and digested, as before, but none is compressed yet.
4. OVERSIZE: the sum of the JSON lengths of all records (the lengths of the entry for the equal records) is compared with `load_max_bytes`, and each encoded JSON with `DEFAULT_BRAIN_VALUE_MAX_BYTES`, before any compress.
5. UNCHANGED: `meta` gets the digest of the merged digests. When `_holds(stored, meta)` is true, `write` sets the TTL again and gives `BrainWrite.UNCHANGED`. With known records and no changed, new or removed record, this step encoded and compressed nothing.
6. Delta: when the store knows the stored records (step 2, or the stored digest is the digest of this snapshot, as `_known` does today), it compresses only the records whose digest differs from the stored digest, checks each compressed value against `DEFAULT_BRAIN_VALUE_MAX_BYTES`, and sends them, the removed numbers and the new `meta` in one WATCH transaction (`_update`). `_update` takes the removed numbers from the digests of the new entry, not from the records that it sends.
7. Replace: in every other case, and when the WATCH transaction of the delta fails, `_replace` encodes, digests and compresses all records, builds its `meta` from that encode, and RENAMEs a temporary key onto the snapshot key, as before. Only `_replace` encodes and compresses all records.

The order of OVERSIZE and OLDER changes: a write that is older and past the bound gives `older` in place of `oversize`. Both write nothing.

`_Seen` keeps a JSON length for each record next to its digest (`lengths: Mapping[str, int]`), which a load takes from its inflated records and a write from its encode. The new `meta` of a delta is the digest of the stored records: an equal record keeps its stored JSON and digest. For records whose equal values give equal JSON, which is true for each record that GitHub, the local file or the shared tier gives (UTC times, one key order), that digest is the digest that a full encode gives. A test shows it: the `meta` after a delta is the `meta` that a new store writes for the same snapshot to an empty fake.

### 2. The compressor is a field of the store

`ValkeySnapshotStore` gets the field `compress: Callable[[bytes], bytes] = zlib.compress`, as #6611 added `load_max_bytes`. `write`, `_update` and `_replace` compress only through it. A test builds the store with a callable that records each JSON that it gets and calls `zlib.compress`. No test patches `zlib` or a devops-cli name (docs/TESTING.md, Doubles). This replaces the patch of `zlib.compress` in the refine design.

### 3. One scan for each repository in a process

`ValkeySnapshotStore` gets `_loads: dict[str, threading.Lock]`, one lock for each `RepoRef(repo).key`, made under `self._lock` (`setdefault`). `records(repo, held)`:

1. reads the `_seen` entry under `self._lock`, and gives its records when their digest is the digest of `held.meta`, with no wait for a lock;
2. reads the clock seam once: the start of the load budget;
3. takes the lock of the repository;
4. reads the `_seen` entry again, and gives its records when their digest is the digest of `held.meta`: the scan of the lane that held the lock gave them;
5. stops when the budget passed (decision 4);
6. else scans, inflates, digests and validates, stores the entry, and gives the records.

Loads of other repositories take other locks and do not wait. A save takes no lock of a repository: the digest check of a load already stops a copy that a write changed during the scan. The dictionary holds one lock for each repository that the process loads, which is the bound of the repositories of the Service.

### 4. The budget covers the wait, the scan, the inflate and the validation

The budget of a load starts at step 2 of decision 3, so a lane that waits for the scan of another lane waits at most one budget. A lane that waits and finds no records after the wait, because the scan of the other lane failed or stopped, stops at once when the budget passed. Thus each lane is bound by one budget, and 13 lanes do not scan one after the other for 13 budgets.

The store checks the clock seam against the deadline after each `HSCAN` step but the last, after the lock (step 5), after each inflated record in `_decompressed`, and after each validated record. A stop logs one info line that names the step, counts `devops_cli_valkey_cache_errors_total{op="hscan",error="budget"}` once, and gives `None`, so the reader takes the local copy or reads GitHub. The `op` label names the Valkey command of the load, `HSCAN`, for each step: the change adds no label value, so the description of the instrument and `docs/TELEMETRY.md` stay true.

### 5. The concurrency test is deterministic

`ClockFake` (`tests/support/fakes/clock.py`) gets `after_each_reading(action)`: the fake runs `action` after each read of the monotonic clock of the seam, as `after_each_sleep` does after a wait. The test builds one store over a client of `valkey_client_on(after_command=...)` that records each `HSCAN`. Thread A loads a shared snapshot of 3 records (one `HSCAN` step). Its `HSCAN` action sets an event and waits, with `THREAD_HANDOFF_BOUND_SECONDS`, for an event that the clock action sets when thread B reads the clock. Thread B starts its load of the same `meta` after the first event. On the head, B reads the clock after it missed the known records and before it takes the lock (decision 3, step 2). So A goes on, stores its records and frees the lock, and B finds them after the lock: one `HSCAN`. On the base, B reads the clock in `_scan` after its miss, and then sends its own `HSCAN`: two. The test has no sleep and no bound on elapsed time. Each wait has the bound of `tests/support/waits.py` and is asserted in the main thread.

The test of a lane that waited past the budget uses the same steps, and the `HSCAN` action of A also moves the `clock` fixture 21 s after the event of B. A stops in its inflate, and B stops after the lock with no scan: one `HSCAN` and two budget stops.

### 6. Time and memory are measured by a scratch script

No test asserts elapsed time (the ast-grep rule `test-elapsed-upper-bound`). A scratch script under `.data/agent/scratch/` loads the local devops-cli snapshot (read only) into a fakeredis server, primes a store, and gives the median time of 5 unchanged saves, on `origin/main` and on the head. It also gives the `tracemalloc` peak of one load, and of two loads of one repository at the same time, before and after. The pull request body gives the numbers. The expected result is a median below 0.2 s on the head.

### 7. No new dependency, and the documents

The change adds no dependency. The documents that it makes wrong change in the same pull request: the module and class docstrings of `listing_shared.py`, the comment of `DEFAULT_BRAIN_SNAPSHOT_LOAD_BUDGET_SECONDS`, and the text of the shared tier in `docs/roadmap/intake.md`. `git grep -n "ValkeySnapshotStore\|_seen\|budget\|unchanged"` over `docs/`, `k8s/README.md` and `openspec/specs/project-brain` gives no other text of the save or the load of the shared snapshot that the change makes wrong.

### 8. Requirement length

Each requirement text of the delta stays under 500 characters, which `uv run openspec validate --all --strict` checks after the archive.

## Rejected alternatives

- **Encode and hash all records, then compare digests.** This is the code on `origin/main`. The measure on the local snapshot gives 0.591 s of `zlib.compress` and 0.087 s of encode and blake2b for 6,638 records, against 0.010 s for a compare of the records.
- **Compare only the stored `meta.digest`.** The digest of the snapshot cannot be known without an encode of each record, so it does not remove the cost.
- **Patch `zlib.compress` in the tests (refine design).** docs/TESTING.md forbids a patch of a devops-cli name, and a patch of the stdlib is a fallback for stdlib edges only. A field of the store is the seam, as `load_max_bytes` is.
- **One lock for all repositories.** It makes the loads of each repository wait for each other. The Service loads 8 repositories.
- **No lock (the code on `origin/main`).** Each lane of a repository scans, inflates and validates its own copy of about 60 MB; the review measured a `tracemalloc` peak of 97.7 MB for one load.
- **cachetools `cached(condition=...)`.** Its waiters call `Condition.wait()` with no timeout (`cachetools/_decorator.py:79`), so the budget cannot bound the wait. It caches each return value, `None` included, so a failed load stays. Each save and removal also changes the known records, which a decorator of the load does not see.
- **Start the budget after the lock.** A lane would wait for the scan of another lane with no bound, and when that scan fails, the waiting lanes would scan one after the other, each for up to one budget.
- **A new `op` value for each step of the load.** It adds label values and a dashboard change for one failure, a load past its budget. The log line names the step.
- **A test that checks the step with a bound on elapsed time.** The ast-grep rule `test-elapsed-upper-bound` refuses it, and a loaded host stretches the time.
