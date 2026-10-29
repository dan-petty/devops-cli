# Design

## Decisions

- **The MCP tool publishes no `servers` option.** `_PATH_PARAM_RESTRICTIONS` lets a command publish some of its options. The command `ai benchmark` gets an entry with the options that stay. A model has no server list to give, so the defect has no input there. A call that names `servers` fails at the argument contract, before any command runs.
- **A list of allowed options, not a list of removed options.** A new option of the command is not published until a person adds it. This is the rule of #2480, #2634 and #2637.
- **The tool keeps `models`, and refuses `model@url`.** The tool exists to compare candidate models, so a tool with no `models` option would benchmark only `ai.model`. A model name has no use for a server, so the tool takes names only. `_check_model_endpoints` runs before dispatch, beside `_check_sandbox_preconditions`. It reads each entry with `parse_model_list` and `parse_model_spec`, the same functions that the command uses, and refuses an entry with an endpoint.
- **The tool benchmarks on the configured servers.** Without `servers`, the command takes `ai.ollama_urls`. The tool needs no way to name one server.
- **The command keeps `--servers` and `model@url`.** A person types them. No model sits between the person and the option, as for `--gateway-url` (#2480). The URL dials at the configured level, as in #2422 and #2481, and #2481 keeps the label `model@host[:port]` as it is.
- **The egress level stays the configured level.** The client admits loopback, and private addresses with `ai.allow_private_network`. The configured servers need it. After this change, no input of a model reaches the client, so no stricter level has an input to guard.
- **The refusal is a check before dispatch, not a schema `pattern`.** See Rejected alternatives.
- **The help text of `--models` says that the MCP tool refuses `model@url`.** The tool description is the help text of the option, so it must be true for the tool. The sentence is short and true for the command too.
- **`ERRORS.mcp.model_names_endpoint` is reused.** It was in the tree with no caller. Its text named an option `model` that the tool does not have and it named the AI key. #954 stops the key already, so the text now names `models` and the requests.
- **The read-only mark stays true.** `CONST_MCP_EXPOSURE_TABLE` marks the tool as read-only, and this change does not touch the table.
- **`SECURITY.md` needs no edit.** Principle 11 states the rule: a tool publishes no option for a URL that a model gives.
- **The tests are in `tests/test_ai_benchmark_mcp_tool.py`.** They call the tool through a FastMCP `Client`, as the tests of #2480 and #2637 do. They use `scripted_resolver` and `record_connects` and read the bytes on the wire. The floor sets `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK`, which outranks the config file, so the level tests set that variable and give the server through the `config` fixture.

## Rejected alternatives

- **Keep `servers` and dial at the public level.** The `EgressLevel.PUBLIC` docstring names this level for a URL that a model gives. But the model could still make the tool send POST requests to any public host, and the public level would refuse the usual loopback Ollama server.
- **Remove `models` from the tool.** This closes the second input with no check, but the tool then benchmarks one model and loses its purpose.
- **A `pattern` on `models` in the tool schema.** `test_every_published_keyword_is_one_a_refusal_can_describe` shows that the refusal layer has no kind or text for `pattern`. Adding them is a second change in the contract layer for one option, and a regular expression would repeat what `parse_model_spec` already knows.
- **Accept a `servers` value only when it is in `ai.ollama_urls`.** The check needs a comparison of URLs, which is a new hand-written helper. The tool needs no way to name a server.
- **An invariant test that no MCP tool publishes a URL option.** Other tools still publish one, and each is an open defect. An invariant needs an allow list of them, and an allow list is an escape.

## Open exceptions

- `vault_status` (`vault_addr`): a private-level GET to any path (#2639).
