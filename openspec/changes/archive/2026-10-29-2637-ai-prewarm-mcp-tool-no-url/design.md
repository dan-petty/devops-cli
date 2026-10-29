# Design

## Decisions

- **The MCP tool publishes no URL.** `_PATH_PARAM_RESTRICTIONS` lets a command publish some of its options. The command `ai prewarm` gets an entry with the options that stay. A model has no URL to give, so the defect has no input. A call that names `url` fails at the argument contract, before any command runs.
- **A list of allowed options, not a list of removed options.** A new option of the command is not published until a person adds it. This is the safe default for a tool that a model calls, and it is the rule of #2480 and #2634.
- **The tool prewarms the configured servers.** Without `url`, `_resolve_prewarm_urls` gives all of `ai.ollama_urls`. With `all_nodes` false, it gives the first one. The tool keeps `all_nodes`, so a model can still choose between the two. The tool needs no way to name one server, because all servers or the first one is the only choice that it needs. The reply of the tool names each server by its configured URL, so a model can see them. #2676 covers this, and it is not part of this change.
- **The command keeps `--url`.** A person types it at the command line. No model sits between the person and the option, as for `--gateway-url` (#2480) and `--url` of the Valkey commands (#2634). The URL dials at the configured level, as `--source` and `--servers` do (#2422).
- **The egress level stays the configured level.** The client of `_preload_single_ollama_url` admits loopback, and private addresses with `ai.allow_private_network`. The configured servers need it: the usual Ollama server is `http://localhost:11434`. After this change, no input of a model reaches the client. So no stricter level has an input to guard.
- **The read-only mark stays false.** `CONST_MCP_EXPOSURE_TABLE` marks the tool as not read-only, and the tool posts and changes the loaded models. The mark is right and needs no change.
- **`SECURITY.md` needs no edit.** Principle 11 states the rule: a tool publishes no option for a URL that a model gives. The POST body of the prewarm holds a model name and a keep-alive value and no credential. So no paragraph for an accepted case is needed, as it was for the Valkey password.
- **The tests are in `tests/test_ai_prewarm.py`.** The file tests the command and the client already. The new tests call the tool through a FastMCP `Client`, as the tests of #2480 do. They use `scripted_resolver` and `record_connects` and read the bytes on the wire. The floor sets `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK`, which outranks the config file. So the level tests set that variable and give the server through the `config` fixture.

## Rejected alternatives

- **Keep the option and dial at the public level.** The `EgressLevel.PUBLIC` docstring names this level for a URL that a model gives. It stops the loopback scan. But the model could still make the tool send a POST request to any public host. The tool needs no URL, because it reports the configured servers. A public level would also refuse the usual loopback Ollama server.
- **Accept `url` only when it equals a server of `ai.ollama_urls`.** The check needs a comparison of URLs, which is a new hand-written helper. `all_nodes` already chooses between all servers and the first one. A second rule on a fix that removes the input is what AGENTS.md rule 2 warns about.
- **Build the request URL from the parts of the base URL.** This would stop the `?x=` trick for a person too. A person who types a URL names the host on purpose. The defect is the model that gives the URL, and this change removes that input.
- **An invariant test that no MCP tool publishes a URL option.** Other tools publish one, and each one is an open defect (see Open exceptions). An invariant needs an allow list of them, and an allow list is an escape. Each fix removes its own tool from the list of defects.

## Open exceptions

These MCP tools still publish a URL or address option that the model fills in. Each has its own issue with a probe.

- `ai_benchmark` (`servers`, `models`): POST requests to any loopback path (#2638).
- `vault_status` (`vault_addr`): a private-level GET to any path (#2639).
