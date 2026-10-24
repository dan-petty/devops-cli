# Proposal

## Why

Issue #2060 is the rest of step B of #1113. #2026 made `valkey.url` keep its scheme and name the address, but three defects stayed:

- Nothing validated `valkey.url` as one URL. Another scheme, a user name or a password in the URL, a bad port, a fragment and an unknown query key were not refused.
- The client did not read the database from the path of the URL, as in `valkey://example.com:6379/2`.
- `valkey.host`, `valkey.port`, `valkey.db`, their environment variables and the `--host` and `--port` options of `devops valkey` named the address a second time. `runs.index_url` had a third parser.

The validated URL refuses the `tcp://` and `http://` URLs that `devops k8s configure-urls` saved as `valkey.url`. So this change also makes `configure-urls` save a `valkey://` URL, which is the item of #1990 (step D of #1113). Without that part, `configure-urls` would save a value that every Valkey reader refuses.

## What Changes

- One function validates each Valkey URL: `valkey.url`, `runs.index_url` and the new `--url` option of the nine `devops valkey` commands. pydantic's `AnyUrl` refuses another scheme, a missing host, a bad port and an IPv6 address with no brackets. Five checks refuse a user name or a password, a fragment, port 0, a query key other than `db`, and a database that is not an integer of 0 or more.
- The message of a refusal names the setting, never quotes the URL, and quotes the scheme it read. For a saved setting it names the commands that write it again: `devops k8s configure-urls` or `devops config set valkey.url` for `valkey.url`, and `devops ai runs connect` for `runs.index_url`.
- The settings check `valkey.url` when a client reads the endpoint, not when they load. A URL that is not valid stops only the Valkey commands, with no traceback. A refused `runs.index_url` keeps each run in the data directory, and the run says why.
- The database comes from the path of the URL, or from the query `?db=<n>`. Each new connection selects it.
- `valkey.host`, `valkey.port`, `valkey.db`, `DEVOPS_CLI_VALKEY_HOST`, `DEVOPS_CLI_VALKEY_PORT`, `DEVOPS_CLI_VALKEY_DB` and the `--host`, `-h`, `--port` and `-p` options of `devops valkey` go, with no shim. `DEVOPS_CLI_VALKEY_URL` and `--url` replace them. An unset or empty `valkey.url` is `valkey://localhost:6379/0`.
- The schemes `redis`, `rediss` and `tcp` go. `valkeys` is the one TLS scheme.
- An old configuration file loads. `save_settings` wrote the default `valkey.host` and `valkey.port` into every saved file. `ValkeyConfig` keeps the pydantic default `extra="ignore"`, as the other sections do, so the loader ignores the removed keys and the next save drops them. A file that named a custom address only in `valkey.host` dials the default URL until a person sets `valkey.url`. A file that `configure-urls` wrote holds a `tcp://` or `http://` URL: the first Valkey command refuses it and names `devops k8s configure-urls`, which now replaces it.
- `devops k8s configure-urls` saves `valkey.url` as `valkey://<host>:<port>`, built with `httpx2.URL`, through the rule of the other service URLs. A saved non-loopback URL survives a loopback detection. A saved loopback URL on a port other than 6379 survives, and a saved URL that is not valid is replaced. The NodePort preview and the port-forward preview show `valkey://`.
- The help of `DEVOPS_CLI_VALKEY_TIMEOUT` names its default, 2.0 seconds.
- A consumer observes the commands, the options, the variables and the messages, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `valkey-endpoint`: one validated URL names the address and the database, `valkeys` is the one TLS scheme, a URL that is not valid is refused, and `configure-urls` saves a `valkey://` URL.

## Impact

- Code: `src/devops_cli/valkey/endpoint.py` (new), `src/devops_cli/valkey/client.py`, `src/devops_cli/config/settings.py`, `options.py`, `env.py`, `defaults.py` and `constants.py`, `src/devops_cli/commands/valkey.py`, `src/devops_cli/commands/k8s/networking.py`, `src/devops_cli/ai/run_store.py`, `src/devops_cli/ui/data_providers.py`, `src/devops_cli/ai/rag/embeddings.py` and `src/devops_cli/security/vulnerability_lookup.py`.
- Docs, generated: `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/CLI_REFERENCE.md`, `docs/commands/valkey.md` and `docs/MCP_TOOLS.md`.
- Tests: `tests/test_valkey.py`, `tests/test_config_cmd.py`, `tests/test_run_store.py`, `tests/test_k8s_networking.py`, `tests/test_k8s_bootstrap.py`, `tests/test_k8s_proxy_addressing.py`, the tests that set the Valkey address, `tests/support/fakes/valkey.py` and the floor configuration in `tests/conftest.py`.
- No manifest, devcontainer file or document outside the generated docs sets `DEVOPS_CLI_VALKEY_HOST`, `DEVOPS_CLI_VALKEY_PORT` or `DEVOPS_CLI_VALKEY_DB` (searched `k8s/`, `.devcontainer/` and `docs/`).

## Feasibility

- pydantic 2.13.5, probed on the base commit: `AnyUrl` with `UrlConstraints(allowed_schemes=["valkey", "valkeys"], host_required=True, default_port=6379)` refuses `redis://`, `rediss://`, `tcp://`, `unix://`, `http://`, `localhost:6380` (scheme `localhost`), ports `99999` and `abc`, `valkey://2001:db8::1:6379` and `valkey://` (empty host). It accepts a user name and a password, a fragment, port 0, `?ssl=true` and the path `/notanint`, so these five need checks. The errors from `errors(include_input=False)` do not quote the input.
- `AnyUrl` keeps the brackets of an IPv6 host, percent-encodes `bücher.example` as `b%C3%BCcher.example`, and writes `::ffff:169.254.169.254` in the normal form `::ffff:a9fe:a9fe`. `urllib.parse.unquote` gives the resolver `bücher.example`. The egress check refuses `::ffff:a9fe:a9fe` as a metadata address.
- valkey-py 6.2.0 `parse_url` reads `redis://`, `rediss://` and `unix://`, and reads `/notanint` as no database. So its parser cannot be the check.
- On the base commit, the probe `Settings.model_validate` with `qdrant.timeout: -1` made `devops config show` end with a pydantic `ValidationError` traceback. A URL type on the field would stop every command the same way, so the check runs when a client reads the endpoint.
- On the base commit, the new tests failed: 14 tests failed and 6 had errors, and `tests/test_valkey.py` could not import `devops_cli.valkey.endpoint`. After the change, they pass.

## Existing Tool Considered

pydantic's `AnyUrl` with `UrlConstraints` parses the URL and refuses the scheme, the host, the port and an IPv6 address with no brackets. A pydantic `TypeAdapter` of a non-negative `int` reads the database. `urllib.parse.parse_qsl` reads the query and `urllib.parse.unquote` decodes the host. `httpx2.URL` writes the URLs that `configure-urls` saves, with the brackets of an IPv6 host. valkey-py sends `SELECT` for the database and does the TLS handshake.

The change builds five checks that no tool makes: a user name or a password, a fragment, port 0, an unknown query key and a database that is not an integer. Cost: about 60 lines of code, about 150,000 tokens to build with its tests, about 10,000 tokens a year to keep and fix, and about 3 hours of elapsed time.

The change deletes `parse_valkey_endpoint` of the client, `_valkey_scheme`, `_parse_valkey_url`, `_normalize_valkey_host` and the validator of `ValkeyConfig`, the `host`, `port` and `db` fields, `DEFAULT_VALKEY_HOST`, `CONST_VALKEY_TLS_SCHEMES`, and `_has_non_default_valkey_port` and `_should_update_valkey` of `configure-urls`.
