# Design

## Context

Three caches keep entries in Valkey: the embeddings engine (`EmbeddingsEngine`), the threat-intel client (`CloudflareRadarClient`) and the library symbol store (`LibraryVectorStore`). Each one also has a tier in memory or on disk, so Valkey is a fail-soft tier: a miss costs only the work that the cache saves. Each cache had its own reaction to a failed command, and none of them could recover. The RAG lookups of a review have a pause of their own, which a hand-written breaker kept. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- One seam at the Valkey boundary of the caches, with the closed, open, cooldown and half-open states of a maintained circuit breaker library.
- A cache that comes back after a Valkey outage, and that sends no command to Valkey in the cooldown.
- The RAG lookup pause on the same library, with the behavior it had.

**Non-Goals:**

- One Valkey client and one breaker for each process, with a short connect timeout (#1992). Each cache builds its own tier here.
- The batch size of the embeddings engine (#2072) and the failover reset of the gateway (#1986).
- The run index (`devops_cli.ai.run_store`), the dashboard and the `devops valkey` commands. They are not caches: each one opens a new client for each use and tells the person when Valkey fails, for example "the run index is unreachable".

## Decisions

- **pybreaker, behind `ValkeyCacheTier`.** The tier wraps a `ValkeyClient` and gives a cache `get` and `set`, which never raise for a Valkey failure. The consumers keep their `valkey_client` parameter and wrap the client that they get, so a test gives a cache a client over the shared Valkey fake. Rejected: a decorator on each method of each cache. Three caches would each hold a breaker and its handling of errors, and a fourth cache would copy them.
- **One failed command opens the breaker.** A failed command can wait the full `valkey.timeout` (2.0 s by default), and a miss costs little. The one-way switch also reacted to the first failure, and #596 records that the open state must be real, because a retry on each call makes each call pay a connection attempt. Rejected: pybreaker's default of 5 failures. Five commands of an outage would each wait the timeout.
- **The cooldown is 60 s.** It is pybreaker's own default `reset_timeout` and the pause of the RAG lookups. With the default timeout, an outage costs at most 2.0 s in each 60 s of cache use. The comment at the default in `src/devops_cli/config/defaults.py` gives this basis.
- **The tier uses `CircuitBreaker.call`, which holds the lock of the breaker while the command runs.** So in the half-open state only one trial goes to Valkey, and in an outage only the first command waits the timeout: the other threads wait for the lock and then find the breaker open. The cost is that the Valkey commands of one cache run one at a time, and a Valkey command takes about a millisecond. Rejected: `calling()`, which runs its block outside the lock. In an outage, each thread of the threat-intel batch (up to 16) would then wait the timeout.
- **A reply error does not open the breaker.** `ValkeyCommandError` comes from a server that answers, for example a `WRONGTYPE` reply or an out-of-memory refusal of a write. The tier lists it in `exclude`, so the read is a miss and the next command goes to Valkey.
- **`throw_new_error_on_trip=False`.** At the trip, pybreaker then raises the `ValkeyError` of the command, and the tier logs it at debug level. A `CircuitBreakerError` then comes only from an open breaker, which the tier skips with no log record, so an open tier does not write a record for each read.
- **The start probe of the engine goes.** The first command finds a Valkey that is down, and the breaker opens. Rejected: keep the probe and open the breaker when it fails. The engine would keep a second client and the literal 0.1 s timeout, which #1992 also removes. The cost: when the configured host does not answer at all, the first command waits `valkey.timeout`, not 0.1 s. A refused port fails at once.
- **The library symbol store goes through the tier in place of `TieredCache`.** #1113 deleted `TieredCache`. The symbol store was the cache that sent each command during an outage, which the issue gives as the defect of `TieredCache`.
- **The RAG pause uses `calling()`, with storage that the investigator keeps.** `calling()` runs the lookup outside the lock, so the lookups of a closed breaker run at the same time, as before. The existing `_ProbeCoordinator` still makes the other lookups wait for one probe, before the first lookup that the model answers and while the breaker is not closed. pybreaker moves an open breaker to half-open only at the first call after the cooldown, so `_lookups_paused` reads the time at which the breaker opened from the `CircuitMemoryStorage` that the investigator gives to the breaker. Thus a lookup in the pause returns before it builds a retriever or asks Qdrant whether it is alive. A permanent `EmbeddingsError` is in `exclude`, so it stops RAG for the run and does not count toward a pause. A listener writes the pause warning when the breaker opens. pybreaker opens the breaker while it handles the failure, so the listener reads that failure with `sys.exception()` and keeps no state of its own.
- **The time comes from `datetime.now`.** pybreaker reads `datetime.now(UTC)` and takes no clock parameter. time-machine, under the `clock` fixture, moves it. Rejected: patch `time.monotonic` in the tests, as the old pause test did. docs/TESTING.md permits a patch of the standard library only when no seam exists.

## Risks / Trade-offs

- [The tier of each cache has its own breaker] → A new `CloudflareRadarClient`, which a review builds for each tool call, starts closed, so it pays one failed command during an outage. The one-way switch did the same. #1992 shares one client and one breaker in each process.
- [pybreaker imports redis and tornado when they are installed] → The development environment installs redis for fakeredis, so a test run imports it. The wheel of devops-cli installs neither, and the modules that import pybreaker do not load for `--help`.
- [Commands of one cache run one at a time] → A Valkey command takes about a millisecond, and the engine reads its Valkey tier one text at a time already.
