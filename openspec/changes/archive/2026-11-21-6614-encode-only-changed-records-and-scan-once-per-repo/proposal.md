# Proposal: #6614

## Why

#6614 removes two costs of the shared listing snapshot in `src/devops_cli/roadmap/stores/listing_shared.py`. The second review of #4668 found them on the real devops-cli snapshot.

1. `ValkeySnapshotStore.write` encodes the JSON of all records, computes their blake2b digests and compresses all of them. Only after that does it decide OLDER, UNCHANGED or a delta. `IncrementalListing.read` saves after each listing read, and the Service runs one thread for each repository and lane. Thus each save of a quiet repository compresses about 38 MB of JSON, and zlib is most of that time.
2. Lanes that load one repository at the same time do not share one scan. `records` holds no lock for the repository, so each lane does the full `HSCAN`, inflate and validation, and keeps its own copy. After a restart, up to 13 of the 14 lanes of devops-cli load in their first round. The load budget covers only the `HSCAN` loop, so the inflate and the validation have no bound in time.

## What Changes

- A save decides OLDER from the schema key and the watermark of the snapshot before it encodes a record.
- A store that knows the stored records compares each record of the snapshot with its known record of the same number before it encodes. An unchanged save encodes, hashes and compresses no record. A delta encodes, hashes and compresses only the changed and new records, and takes the digests of the other records from its known records, so its new `meta` names the records that Valkey holds. Only a write to a temporary key (`_replace`) encodes and compresses all records.
- `ValkeySnapshotStore` takes its compressor as the field `compress` (default `zlib.compress`), so a test counts its calls through the public interface.
- A load takes a lock for its repository before it scans. A load that waited reads the known records again, so two lanes of one repository at the same time send one `HSCAN` scan.
- The load budget starts when a load misses its known records. It covers the wait for the scan of another lane, the `HSCAN`, and the inflate and validation of the records. Each stop counts the existing `devops_cli_valkey_cache_errors_total{op="hscan",error="budget"}`.
- `ClockFake` of `tests/support/fakes/clock.py` gets `after_each_reading`, a test action after each read of the monotonic clock, so a test sees that a thread reached the start of its load budget.
- The change alters what a consumer observes (the commands that two lanes send to Valkey, and when a load stops and counts its budget), so it carries a spec delta.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-brain/shared-cache`: "The lanes of one process scan a shared copy once" (loads at the same time share one scan), "A shared load has a budget" (the budget covers the wait, the `HSCAN`, the inflate and the validation), and the new requirement "A save compresses only the records that it sends".

## Impact

- Code: `src/devops_cli/roadmap/stores/listing_shared.py`, and the comment of `DEFAULT_BRAIN_SNAPSHOT_LOAD_BUDGET_SECONDS` in `src/devops_cli/config/defaults.py`.
- Tests: `tests/roadmap/stores/test_listing_shared.py`, and the test support `tests/support/fakes/clock.py`.
- Documents: `docs/roadmap/intake.md`. `docs/TELEMETRY.md` does not change: the change adds no label value, and the description of `devops_cli_valkey_cache_errors_total` stays true.
- Runtime: no new dependency, no new setting and no manifest change. An unchanged save of the devops-cli snapshot sends the same commands as before and compresses no record. A store keeps one lock and one dictionary of record JSON lengths for each repository that it loads or saves.
- The change fits one pull request.

## Feasibility

Each premise was checked on 2026-11-21 against `origin/main` at 3f8f7a90e, after the merge of #6611 (9d8ee8742):

- Defect 1: in `src/devops_cli/roadmap/stores/listing_shared.py`, `write` (`:318`) encodes each record (`:322`), compresses each record (`:331`) and digests each record (`:339`), and only then decides OLDER (`:345`) and UNCHANGED through `_holds` (`:348`).
- Defect 2: `records` (`:253`) holds `self._lock` only to read `_seen` (`:259`) and to store it (`:282`). The `_scan` call (`:264`) holds no lock for the repository.
- Defect 3: `_scan` (`:286`) reads the clock at its start (`:290`) and checks the budget only between two `HSCAN` steps (`:301`). `_decompressed` (`:459`) and the validation (`:271` to `:275`) read no clock, and a scan of fewer fields than `DEFAULT_BRAIN_SNAPSHOT_SCAN_COUNT` (500) checks no budget.
- No open pull request names 6614 (`search/issues?q=repo:dan-petty/devops-cli+is:pr+is:open+6614` gives 0), and no Job of the `devops` namespace names 6614.
- A measure on the local devops-cli snapshot (read only), with the median of 3 runs of each step: 6,638 records and 38,098,792 bytes of JSON; encode 0.052 s, blake2b 0.035 s, `zlib.compress` 0.591 s, and a compare of each record with the record of the same number of a second copy (`==`) 0.010 s. Thus zlib is most of the cost of an unchanged save, and a compare before the encode is cheap.
- `IssueRecord` is a frozen model (`src/devops_cli/roadmap/stores/store.py:726`) of values and tuples. Its `job_record` is a `dict`, and no code changes it in place: `git grep -nE "\.job_record\[[^]]+\]\s*=|\.job_record\.(update|pop|setdefault|clear)\(" -- src` gives no line. So a known record that is equal to a record of the snapshot keeps its JSON.
- fakeredis 2.40.0 holds its server lock only while it does a command (`fakeredis/_socket/_base.py:252`), and the `after_command` action of `valkey_client_on` runs after that. So a test can hold the `HSCAN` of one thread while a second thread sends commands.

## Existing Tool Considered

- cachetools 8.0.2 (in `uv.lock`, MIT, maintained) gives `cached(cache, condition=...)`, which lets one thread compute a key while the others wait. It does not fit the scan of a repository: its waiters call `Condition.wait()` with no timeout (`cachetools/_decorator.py:79`), so the load budget cannot bound the wait; it caches each return value, `None` included, so a failed or stopped load would stay in the cache; and each save and removal also changes the known records, which a decorator of the load does not see.
- The standard library gives what the change needs: `threading.Lock` for the lock of each repository, and `zlib` and `hashlib`, which the module already uses. The alternatives check of the issue gives `not-applicable` (class perf, no tool found).
- Written cost of the project code: about 80 lines of source and 200 lines of tests, about 50,000 tokens to build, 3,000 tokens a year to keep and 8,000 tokens to fix, and 4 hours of elapsed time.
- Internal code that the change deletes: the encode, digest and compress of all records at the start of `write`, and the check of `_holds` on a full encode when the store knows the stored records.
