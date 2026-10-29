# Design

## Decisions

- **The MCP tools publish no URL.** `_PATH_PARAM_RESTRICTIONS` already lets a command publish some of its options. The three gateway commands get an entry each: `provider` for `status` and `routes`, `backend` for `probe-backend`. The tools query the configured gateway and the first of `ai.ollama_urls`. A model has no URL to give, so the egress defect has no input. A call that names `gateway_url` or `backend_url` fails at the argument contract, before any command runs.
- **The commands keep their URL options.** A person types `--gateway-url` and `--backend-url` at the command line. These URLs dial at the configured level. `--source` of `devops ai cost update-pricing` and `--servers` of `devops ai benchmark` do the same (#2422). No model sits between the person and the option, so no input needs a stricter level.
- **The key rule is where the header is attached.** `_query_model_info` calls `_key_for`. It gives the key only when the origin of the URL is the origin of `ai.gateway_url` or `ai.portkey_url`. Every caller of `fetch_model_info` gets the rule: the router, the tuning sweep, the run store and the reasoning check of the OpenAI client. A caller passes its `ai_config`. Without one, the function reads the loaded settings, as `configured_level` does.
- **An origin is the scheme, host and port.** `httpx2.URL.origin` gives them, and it normalizes the case of the host and the default port. The path is not part of the origin. So `--gateway-url http://example.com:4000/another/path` still gets the key.
- **Both gateway URLs count as configured.** Under the Portkey provider, the router queries `ai.portkey_url`. A rule for `ai.gateway_url` alone would take the key from that query.
- **A refusal says that the gateway got no key.** When a gateway of another origin answers HTTP 401 or 403 and a key is set, "no API key is configured" would mislead. `fetch_model_info` raises an `AICredentialsError` that names the host and port of the gateway. It gives no URL, because a URL can hold user information.
- **The tests are in `tests/test_ai_gateway.py`.** The file already tests these commands and tools. The new tests use `scripted_resolver` and `record_connects`, and read the bytes on the wire. The floor sets `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK`, which outranks the config file. So the level tests set that variable and give the URLs through the `config` fixture.
- **`SECURITY.md` gets principle 11.** The lesson is general. A URL from a model is untrusted input, and a credential goes only to the origin that the configuration names.

## Rejected alternatives

- **Keep the MCP options and dial them at the public level.** The `EgressLevel.PUBLIC` docstring names this level for a URL that a model gives. It stops the loopback scan. But the model could still make the tool send a GET request to any public host. `probe-backend` returns up to 256 characters of the error and the model names. No tool needs the option, because each one reports the configured service.
- **Give the URL option of the command line the public level too.** The tools were the only path from a model to the option. A public level for a person would also refuse a gateway that the person runs on loopback. `--source` and `--servers` dial at the configured level for the same person.
- **Put the rule in the router only.** The first version of this change did so. `fetch_model_info` and `tune_pool` still sent the key to any URL, and `devops ai gateway tune --gateway-url` could send the key to another host. The rule belongs where the header is attached.
- **Compare only the host, or test the start of the URL.** A port that starts with the configured port, such as `:40000` for `:4000`, starts with the configured URL. A different port or scheme is a different service. The origin of httpx2 has these cases right, and the test rows hold each of them.
- **An invariant test that no MCP tool publishes a URL option.** Other tools publish one, and each one is an open defect (see Open exceptions). An invariant needs an allow list of them, and an allow list is an escape. Each fix removes its tool from the list of defects.

## Open exceptions

These MCP tools still publish a URL or address option that the model fills in. Each has its own issue with a probe.

- `valkey_*` (`url`): the Valkey password goes to the URL (#2634).
- `k8s_logs` (`loki_url`): a private-level GET to any path, with the answer text returned (#2635).
- `ai_prewarm` (`url`): a POST to any loopback path (#2637).
- `ai_benchmark` (`servers`, `models`): POST requests to any loopback path (#2638).
- `vault_status` (`vault_addr`): a private-level GET to any path (#2639).
