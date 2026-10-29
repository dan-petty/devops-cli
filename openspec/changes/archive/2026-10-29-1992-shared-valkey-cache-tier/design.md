# Design

## Decisions

- **One tier, not one client.** The caches share the `ValkeyCacheTier`, so they share its breaker as well as its client. With a shared client and a breaker for each cache, each cache would still spend its own connection attempt in an outage.
- **Built on first use, under a lock.** Engines are built on worker threads during a review. A lock keeps two threads from building two tiers. `functools.cache` would not stop that race.
- **Fail soft on the project's errors only.** `shared_cache_tier` catches `DevOpsCLIError`: a `valkey.url` that is not valid (`ConfigurationError`), a locked keyring, a settings error. Any other error is a defect and is raised.
- **Connect timeout `min(valkey.timeout, 0.25)`.** A user who sets a shorter `valkey.timeout` keeps it for connections too.
- **The library store takes the tier.** A store that took a client would build its own tier and its own breaker.

## Rejected alternatives

- **A process-wide `ValkeyClient` and a tier for each cache.** Each tier keeps its own breaker, so each cache dials once in each cooldown. The test `test_while_valkey_refuses_a_second_cache_dials_nothing_in_the_cooldown` refuses that.
- **A connect timeout as a new setting.** No one asked for it, and the measured connects are under 1 ms. #1992 asks for a constant in `defaults.py`.
- **Keeping the ping in `devops ai ingest`.** The ping cost one more connection, and the tier already fails soft.
