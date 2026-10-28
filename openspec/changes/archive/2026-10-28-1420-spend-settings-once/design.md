# Design

## Decision

`is_local` makes one `_SettingsOnce` for each call and passes it down. `_SettingsOnce.value` is a `functools.cached_property` that calls `load_settings` on first use and returns None when the settings cannot load. The helpers that need the configured domains and AI servers read `value`; the helpers that decide by address or name do not, so a local address or a name that is not public loads nothing.

## Rejected alternatives

- **A process-wide cache of the configured hosts.** It would make a request load nothing, but a change to `config.yaml` in a running process (the Service, a long review) would not take effect. `load_settings` already caches the files by their stamp and re-reads a changed file, so one load for each request keeps that rule.
- **Pass the client's settings to `track_request_spend`.** The clients hold an `AIConfig`, not the `k8s` and `cloudflare` domains that the locality check needs, and `track_request_spend` has six call sites in `ai/client/`, `ai/spend/`, `ai/rag/` and `roadmap/`. Each would need the whole `Settings`. The gain over one load for each request is 4.4 ms, and the signature change touches every caller.
- **One ledger connection for each process.** Opening a connection costs 0.58 ms of the 14.6 ms that `record_request` takes. A shared `sqlite3.Connection` with `check_same_thread=False` needs a lock around every use, because the gateway clients record spend from several threads, and it must survive `reset_ledger` and its `VACUUM`. The gain does not pay for that risk.
