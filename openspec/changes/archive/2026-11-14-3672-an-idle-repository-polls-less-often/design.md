# Design

## Decisions

**The job reports the state, not the engine.** The lane job already opens the store and reads the listing, so it answers `open_items` and `open_pulls` from that read. The engine keeps a small thread-safe set of idle repositories; a per-repo GitHub read in the tick loop would spend the very requests that the setting saves.

**The tick keeps the normal cadence and skips a repository until its interval is due.** `poll_interval()` stays the budget-aware normal interval, so the loop never sleeps longer than a busy repository needs. Each tick polls only the repositories whose interval has passed. An idle repository polls at its next tick after 600 seconds.

**The idle state is the last round's answer.** A webhook clears the entry, so the next round reads the new work and reports the state again. A repository whose rounds fail keeps its last state; a failed round changes nothing.

**The validation names both settings.** An idle interval below the normal one would poll an idle repository more often than a busy one, and the error tells which two settings conflict.

## Rejected alternatives

- **A per-repository GitHub read in the tick loop.** It spends a request per repository per tick to save requests.
- **A second timer per repository.** It duplicates the one tick loop and its budget handling.
- **A fixed long interval for every repository.** A busy repository would then miss webhook-free work for minutes.
