# Design

## Decisions

- **The MCP tool publishes no Loki URL.** `_PATH_PARAM_RESTRICTIONS` lets a command publish some of its options. `("k8s", "logs")` gets an entry with every option but `loki_url`. A model has no URL to give, so the defect has no input. A call that names `loki_url` fails at the argument contract, before the command runs.
- **A list of allowed options, not a list of removed options.** This is the rule of the table that #2480 made. A new option of `devops k8s logs` is not published until a person adds it.
- **The tool dials the default Loki.** The command has no Loki setting and opens no port-forward. A person who gives no `--loki-url` gets `DEFAULT_LOKI_URL`, and the tool now does the same. This is the address that the tool used for each call without `loki_url`, so a call that gave no URL does not change. The request path is fixed, so the model controls only the query, `since` and `limit` of the request. If that Loki does not answer, the tool runs `kubectl logs`, as before.
- **The command keeps `--loki-url`.** A person types it at the command line. No model sits between the person and the option, as in #2480 and #2634. The requirement "Egress policy enforcement for Loki" keeps its words, because it is about the command and the client.
- **The Loki client keeps the private level.** Loki is an internal service of the cluster, reached through a port-forward on the host. The level `EgressLevel.PUBLIC` would refuse the usual address. With a fixed URL, the level is no longer a defence against a model.
- **The answer that the tool returns is the answer of the default Loki.** After the change, the text of an error and the log lines come from `DEFAULT_LOKI_URL` only. That is the purpose of the tool. No model input chooses the host or the path.
- **No new `loki.url` setting in this change.** A setting is a feature. It needs a key in the settings model, the generated configuration documents, the wizard and a rule for an unset key. It does not remove the defect, because the defect is the input of the model. The error texts of the fallback name a `loki.url` setting that does not exist. This is a separate defect, and it has its own issue (see Workflow follow-up in the tasks).
- **`SECURITY.md` is not changed.** Principle 11 says that a tool publishes no option for a URL from a model. It holds no list of open exceptions.
- **The tests are in `tests/test_k8s_logql.py`.** The file tests the Loki client and the query engine already. The new tests call the tool through a FastMCP `Client`, as the gateway tests of #2480 do. They use `scripted_resolver` and `record_connects` from `tests/web_fakes.py` and read the bytes on the wire. The `k8s` domain is withheld from the tool listing, so each test hydrates it first.

## Rejected alternatives

- **Keep the option and dial at the public level.** The `EgressLevel.PUBLIC` docstring names this level for a URL that a model gives. It stops the loopback and private scan. But the model could still make the tool send a GET request to any public host with a path of its choice. It would also refuse the usual Loki address (`localhost:3100`). The tool needs no URL, because it reports the default Loki.
- **Check the path or the host of the URL that the model gives.** A host list or a path check is a second rule on an input that the fix removes. The defect is that a model gives an address at all. AGENTS.md rule 2 warns about a fix on a fix.
- **Add a `loki.url` setting and make the tool use it.** See the decision above. It is a feature with its own surface, and the rules of this tool (a fixed address from the configuration) hold with the default address also.
- **An invariant test that no MCP tool publishes a URL option.** Other tools publish one, and each one is an open defect: #2637 for `ai_prewarm`, #2638 for `ai_benchmark` and #2639 for `vault_status`. An invariant needs an allow list of them, and an allow list is an escape. Each fix removes its own tool.
