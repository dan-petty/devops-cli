# Design

## Decisions

- **The label is `host[:port]` of the origin.** `server_label(url)` returns `origin_label(get_url_origin(url))`, the text that the AI client writes for the server of a reply. A URL with no origin gives `unknown` (`CONST_AI_BACKEND_HOST_UNKNOWN`), as `LLMClient.backend_host` does. The helper is 3 lines and builds no parser.
- **The helpers sit in `ai/benchmark/`.** The client composes the same two calls inside `LLMClient`, which needs a built client. A dry run has no client, and the embedding runner builds its engine late. Thus the benchmark package has its own small helper, and `ai/client/` stays as it is.
- **The runner keeps the URL and writes the label.** `self.servers` holds the configured URLs because the client needs the userinfo to send Basic authentication. The label is made where a name is written: the `Workers:` line, the progress text, the `server` fields and the summaries. The saved report and the kept run get the label through the report.
- **A `--servers` value is handled like a configured URL.** The runners take it as a list of URLs. The setup of the kept run lists the sorted labels.
- **A `model@endpoint` entry is named `model@host[:port]`.** `model_label` splits the entry with `parse_model_spec` and names the endpoint with `server_label`. An entry with no endpoint keeps its model name. `BenchmarkRunner.models` holds the labels, and so every report field that holds a model. The runner keeps a map from each label to its entry. `_client_for_model` reads the entry from it, so the client still gets the userinfo.
- **The embedding benchmark already drops the endpoint from the model.** Its result names the model without the endpoint, and its `server` is the label of the endpoint. Only the setup of the kept run held the entry, so `_benchmark_setup` writes `model_label` of each `--models` entry for both benchmarks.
- **Two servers can have one label.** Two URLs with the same host and port have one label, also when they differ by userinfo, by path or by scheme. They share one server summary, and the `Workers:` line shows the label twice. This is accepted: the label names the host that answered, and a path or an account is not a node. A name that holds the account or the path would put a part of the secret back in the report.
- **Two models can have one label.** Two `--models` entries with the same model and the same host and port share one label. The runner uses the first of them for the requests. This is accepted for the same reason.
- **The `default` server stays.** The embedding runner uses the text `default` when no server is configured. It is not a URL, so the runner keeps it as it is.
- **An error names a server by its label.** The masking of a `DevOpsCLIError` message hides a password and not a user name alone. A token can be a user name, so the benchmark builds its error texts from `server_label` and never from the URL. These are the refused `--servers` entry, the refused embedding endpoint and the endpoint that is not the gateway. A refused `--servers` entry is named by its position and its label (`--servers entry 2 (example.com:2121)`), because `unknown` alone does not say which entry is wrong.
- **The engine names its endpoint without userinfo.** The `error` of a failed embedding run is the message of `EmbeddingsError`, and the engine builds it from the URL of the request. The benchmark cannot rebuild that text, so the fix is in `ai/rag/embeddings.py`. `_endpoint_text` takes the userinfo from the URL with `httpx2.URL.copy_with` for the errors, their `details` and the log lines. The request still goes to the URL with the userinfo. A URL that httpx2 cannot read shows as `unknown`.
- **The sanitizer stays.** It masks the password of a URL and not a user name alone. Masking every user name would also change `ssh://git@example.com`. The choice belongs to a person, and #2662 asks for it. This change does not depend on the choice, because it never gives a URL with userinfo to a message.
- **Old files stay.** Saved reports and kept runs from before this change hold the URL as it was configured. The project keeps no backward compatibility before 1.0.0, so this change does not rewrite them. The pull request body tells a person who configured a password in a server URL to change it and to delete these files.

## Rejected alternatives

- **Replace `self.servers` with labels when the runner starts.** The client takes its endpoint from `self.servers`, and it needs the userinfo. A probe with a stubbed Ollama showed `Authorization: Basic` on each request. A label would send no authentication, and an Ollama behind a proxy would answer 401.
- **Keep the entry as the key of the model, and label it at each write.** The key joins the responses to the grades, and the leaderboard reads it. A label made late would need each write point to know the map. One label from the start makes the report one set of names.
- **Mask the userinfo in the text with `mask_secrets`.** The text stays the data model and keeps the host, the path and the scheme. The origin gives only the host and the port, so no later reader can parse a secret out of it.
- **A new parser for the label.** `get_url_origin` and `origin_label` already read the URL as httpx2 sends it. #1107 and #1112 move every read of an address to the sending client's parser.
- **Refuse userinfo in the settings.** It breaks working Basic authentication. #1000 owns the validation of URL settings.
- **The scheme in the label (`http://example.com:11434`).** It does not match the text of the replies and the ledger, which show `host[:port]`.

## Non-goals

- `src/devops_cli/security/sanitizer.py` masks the password of a URL and not a user name alone: #2662.
