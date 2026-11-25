# Proposal

## Why

Issue #2026: a `valkeys://` or `rediss://` URL in `valkey.url` connected in plaintext. The settings model derived `valkey.host` and `valkey.port` from the URL and dropped the scheme. Each Valkey client that reads the settings got only the host and the port, so it did not dial TLS. Only the `host` argument of `ValkeyClient`, which `runs.index_url` uses, dialled TLS after #1988.

A second defect hid the address of the URL. Every save of the settings writes the default `valkey.host` and `valkey.port` to the configuration file. The model let those keys win over `valkey.url`, so a URL added to a saved file did not change the address that the client dialled.

This change is step B of #1113 in part: the URL keeps its scheme and names the address. The rest of step B is a follow-up (see tasks.md).

## What Changes

- `ValkeyConfig.endpoint` gives the endpoint that a Valkey client dials: `valkey.host` behind the scheme of `valkey.url`. The `devops valkey` commands, the Valkey panel of the dashboard, the embedding cache and the Cloudflare Radar cache dial it. A `valkeys` or `rediss` scheme dials TLS through the `_VettedSSLConnection` of #1988. That connection sends the URL host as the server name and checks the certificate against it. A `valkey` scheme dials plaintext.
- A `valkey.url` with a Valkey scheme sets `valkey.host` and `valkey.port` from its host and port, also when the same file holds `valkey.host` and `valkey.port`. A value with another scheme, such as the `http://` URL that `devops k8s configure-urls` can save, only fills a missing `valkey.host` and `valkey.port`, as before.
- An environment override `DEVOPS_CLI_VALKEY_HOST` still replaces the host. The endpoint puts the scheme of `valkey.url` in front of it, unless the override names a Valkey scheme of its own.
- The `url` row of the `valkey` table in `docs/CONFIGURATION.md` tells how the URL names the address and how the scheme decides TLS.
- The change alters which address a `devops valkey` command dials and whether it uses TLS. A consumer observes both, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `valkey-endpoint`: the endpoint that the Valkey clients of devops-cli dial from the `valkey` settings, and when that connection uses TLS.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/config/settings.py` (`ValkeyConfig.endpoint`, `_valkey_scheme` and `_parse_valkey_url`), and the four readers of the settings: `src/devops_cli/commands/valkey.py`, `src/devops_cli/ui/data_providers.py`, `src/devops_cli/ai/rag/embeddings.py` and `src/devops_cli/security/vulnerability_lookup.py`.
- Docs: `docs/CONFIGURATION.md`, generated.
- Tests: `tests/test_valkey.py` (`TestValkeyUrl`) and `tests/test_ui_dashboard.py`.

## Feasibility

- A probe on the base commit, with valkey-py 6.2.0, built a `ValkeyClient` from `ValkeyConfig.model_validate({"url": "valkeys://example.com:6380"})` as the readers do. The model gave the host `example.com:6380`, and the client pool used `_VettedConnection`, the plaintext class. The same URL in the `host` argument gave `_VettedSSLConnection`.
- A second probe showed that `Settings().model_dump(mode="json", exclude_none=True)["valkey"]`, the data that `save_settings` writes, holds `host: localhost:6379` and `port: 6379`. With `url: valkeys://cache.example.com:6380` added, the model gave the host `localhost:6379`.
- The TLS path exists: #1988 made `ValkeyClient` choose `_VettedSSLConnection` with `ssl_check_hostname=True` for a `valkeys` or `rediss` scheme in its `host` argument. The library source shows that `SSLConnection` sends `self.host` as the server name. So the fix gives the readers the scheme, and builds no TLS code.
- On the base commit, the new tests failed: 14 tests failed and 4 had errors. After the change, they pass.

## Existing Tool Considered

`urllib.parse.urlsplit` of the standard library reads the scheme, as it reads the host and the port already. The TLS connection, the server name and the certificate check come from valkey-py `SSLConnection`, through the `_VettedSSLConnection` of #1988, and the platform CA store. Nothing is built.

`pydantic.AnyUrl` with `UrlConstraints`, which #1113 names for a validated URL, was not used here. It refuses values that the settings accept today, and that refusal belongs to the follow-up that removes `valkey.host`, `valkey.port` and `valkey.db`.

The change deletes the scheme check that `_parse_valkey_url` and `_normalize_valkey_host` each wrote out, which `_valkey_scheme` replaces. It also deletes the `getattr` fallbacks and the `DEFAULT_VALKEY_HOST` and `DEFAULT_VALKEY_PORT` imports of `fetch_valkey_status`.
