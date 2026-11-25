# Design

## Context

`ValkeyConfig` in `src/devops_cli/config/settings.py` holds `valkey.url`, `valkey.host` and `valkey.port`. Its validator derives `valkey.host` and `valkey.port` from `valkey.url`. Four readers build a `ValkeyClient` from the settings: `_resolve_client` of the `devops valkey` commands, `fetch_valkey_status` of the dashboard, `EmbeddingsEngine._init_valkey` and `CloudflareRadarClient`. `ValkeyClient` dials TLS when the scheme of its `host` argument is `valkeys` or `rediss` (#1988). See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- The scheme of `valkey.url` decides TLS for each reader of the settings.
- The host and the port of `valkey.url` are the address, also in a saved configuration file.

**Non-Goals:**

- Refuse a URL that is not valid, remove `valkey.host`, `valkey.port` and `valkey.db`, and read the database of the URL. These are the rest of step B of #1113, a follow-up.
- Save `valkey.url` as a `valkey://` URL in `devops k8s configure-urls` (#1990).
- Share one client between the caches (#1992).

## Decisions

- **One property gives the endpoint, and each reader dials it.** `ValkeyConfig.endpoint` puts the scheme of `valkey.url` in front of `valkey.host`. Rejected: keep the scheme in `valkey.host`. An environment override assigns `valkey.host` with no validation (`_apply_env_overrides` calls `dotted_set`, which calls `setattr`), so the override would drop the scheme and dial plaintext. The property puts the scheme of the URL in front of the override, so a mismatch fails the certificate check. Rejected: give `ValkeyClient` a TLS flag. The client already reads TLS from the scheme of its `host` argument, and a second input could disagree with it.
- **A URL with a Valkey scheme sets the host and the port.** Every save writes the default `valkey.host` and `valkey.port`, as the probe in proposal.md shows. With the old precedence, the URL host did not reach the client, and a `valkeys` URL would check the certificate against `localhost`. Rejected: the endpoint is `valkey.url` itself when it is set. Then `DEVOPS_CLI_VALKEY_HOST` would not replace the host of a URL in the file. The settings load in the order file, then environment, and each layer wins (`load_settings`).
- **A URL with another scheme keeps the old precedence.** `devops k8s configure-urls` can save `valkey.url` as `http://<node>:<port>`, beside a `valkey.host` that it derives from the same address. Such a URL fills only a missing host and port, and the endpoint is `valkey.host`. Before, such a URL also did not override the saved host. #1990 makes the command save a `valkey://` URL.
- **A host that names a Valkey scheme keeps it.** `DEVOPS_CLI_VALKEY_HOST=valkeys://example.org:6381` reaches `valkey.host` as written. The endpoint uses that value as it is, as the client got it before. A scheme in front of it would give a value that the client cannot read.

## Risks / Trade-offs

- [A file holds a `valkey.url` and a different `valkey.host` on purpose] → The URL now wins. A person who wants the other host removes `valkey.url` or sets `DEVOPS_CLI_VALKEY_HOST`.
- [A `valkeys` URL reaches a server with no certificate for its host] → The handshake fails and the command names the certificate error. The client sends no command.
