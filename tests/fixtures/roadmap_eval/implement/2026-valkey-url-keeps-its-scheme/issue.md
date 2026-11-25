## Friction

`valkey.url` reaches the Valkey client as a host and a port, because the connection config drops the scheme. So a `valkeys://` or `rediss://` URL in `valkey.url` still connects in plaintext. Only the `host` argument path, which `runs.index_url` uses, dials TLS since #1988.

## Evidence

Step B of tracking issue #1113 ("one validated URL names every Valkey endpoint") has no child issue. Intake refused it on 2026-10-23 as a duplicate of #1113. #1988 delivered step C and names this follow-up in its task file.

## Proposed remedy

- Parse `valkey.url` once with `urllib.parse`, keep its scheme, and pass it to the client, so `valkeys` and `rediss` dial TLS with host name checks.
- A test with a `valkeys://` URL shows a TLS handshake against a local CA, and a test with `valkey://` shows plaintext.
