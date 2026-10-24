# Design

## Context

After #2026, `ValkeyConfig` held `url`, `host`, `port` and `db`, and a validator derived `host` and `port` from the URL. `ValkeyClient` took a host, a port and a database, and parsed the host again with `parse_valkey_endpoint`. `RunIndex.connect` gave `runs.index_url` to that host argument. The nine `devops valkey` commands took `--host` and `--port`. `devops k8s configure-urls` saved `valkey.url` with the scheme `tcp` or `http`. See proposal.md for the defects.

## Goals / Non-Goals

**Goals:**

- One function validates each Valkey URL and gives the scheme, the host, the port and the database.
- `valkey.url`, `runs.index_url` and `--url` are the only places that name a Valkey address.
- `configure-urls` saves a URL that the readers accept.

**Non-Goals:**

- One shared fail-soft client for the caches (#1992). A refused `valkey.url` turns the caches off, as an unreachable Valkey does.
- A setting for a private CA. The platform CA store and `SSL_CERT_FILE` stay the trust (decision 3 of #1113).

## Decisions

- **The client takes a validated endpoint, not a string.** `parse_valkey_url(value, setting=...)` returns a `ValkeyEndpoint`, and `ValkeyClient(endpoint, password=..., timeout=...)` dials it. Only the caller knows the setting that the message must name. Rejected: the client parses a URL string. Then the client must know the key of each caller, or give a message with no key.
- **The settings check the URL when a client reads it.** `ValkeyConfig.url` stays a string, and the `endpoint` property validates it. Rejected: the field type `AnyUrl`. On the base commit, a value that a field refuses made `devops config show` end with a pydantic traceback, so a bad `valkey.url` would stop every command, also those that use no Valkey.
- **pydantic `AnyUrl` plus five checks.** Rejected: valkey-py `parse_url`. It reads `redis://`, `rediss://` and `unix://`, and reads `/notanint` as no database (probed with valkey-py 6.2.0). Rejected: `urllib.parse.urlsplit` alone. It needs its own checks for the scheme, the port and an IPv6 address with no brackets, which `AnyUrl` already makes.
- **No message quotes the URL.** A refused URL can hold a password. The message quotes only the scheme or the query key it read, and the parser raises with no cause, because a pydantic error quotes its input.
- **The removed keys load and are dropped.** `ValkeyConfig` keeps the pydantic default `extra="ignore"`. Rejected: `extra="forbid"`. Every file that a save wrote holds `valkey.host` and `valkey.port`, so every command would fail to load the settings. Rejected: a warning or a reader for the old keys. That is a shim, and AGENTS.md allows no shim before 1.0.
- **`--url` replaces `--host` and `--port`.** The short option `-h` of `--host` was also the help option of every command.
- **A refused `runs.index_url` is an index that is not configured.** `RunIndex.from_settings` raises `RunIndexNotConfiguredError` with the message of the refusal. `record_run` then keeps the run in the data directory and reports why, as for no index. Rejected: let `ConfigurationError` go up. It would stop a benchmark after its run.
- **`configure-urls` writes `valkey://` in the same change (#1990).** Service detection gives `http://` for a NodePort or a load balancer. `_as_valkey_url` writes the detected host and port as `valkey://` with `httpx2.URL`, and `valkey.url` goes through `_apply_service_url`, as `qdrant.url` goes. A saved loopback URL on a port other than 6379 survives (decision 5 of #1113). A saved URL that is not valid is replaced, so a `tcp://` value that the command saved before is repaired by the command that the refusal names. Rejected: leave the writer to #1990. Between the two merges, `configure-urls` would save a value that every reader refuses.

## Risks / Trade-offs

- [A file names a custom Valkey only in `valkey.host`] → The client dials `valkey://localhost:6379/0`. A person sets `valkey.url`.
- [A file holds the `tcp://` URL that `configure-urls` saved] → The Valkey commands refuse it, name `devops k8s configure-urls`, and the caches stay off until a person runs it or sets `valkey.url`.
- [The URL parser writes an IPv6 address in its normal form] → A message can show `::ffff:a9fe:a9fe` for `::ffff:169.254.169.254`. The address is the same.
