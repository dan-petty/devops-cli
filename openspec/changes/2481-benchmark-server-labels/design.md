# Design

## Decisions

- **The label is `host[:port]` of the origin.** `server_label(url)` returns `origin_label(get_url_origin(url))`, the text that the AI client writes for the server of a reply. A URL with no origin gives `unknown` (`CONST_AI_BACKEND_HOST_UNKNOWN`), as `LLMClient.backend_host` does. The helper is 3 lines and builds no parser.
- **The helper sits in `ai/benchmark/`.** The client composes the same two calls inside `LLMClient`, which needs a built client. A dry run has no client, and the embedding runner builds its engine late. Thus the benchmark package has its own small helper, and `ai/client/` stays as it is.
- **The runner keeps the URL and writes the label.** `self.servers` holds the configured URLs because the client needs the userinfo to send Basic authentication. The label is made where a name is written: the `Workers:` line, the progress text, the `server` fields and the summaries. The saved report and the kept run get the label through the report.
- **A `--servers` value is handled like a configured URL.** The runners take it as a list of URLs. The setup of the kept run lists the sorted labels.
- **The endpoint of a `model@endpoint` entry gets the label in the embedding benchmark.** The result names the model without the endpoint, and its `server` is the label of the endpoint. The chat benchmark keeps the entry as the name of the model. #2643 asks for that change.
- **Two servers can have one label.** Two URLs with the same host and port and different userinfo have the same label, so they share one server summary. The label names the host that answered, and the userinfo names an account. This is accepted. A name with the account would put a part of the secret back in the report.
- **The `default` server stays.** The embedding runner uses the text `default` when no server is configured. It is not a URL, so the runner keeps it as it is.
- **The error texts stay.** An error of the runners or of the command is a `DevOpsCLIError` message, which masks userinfo when it is made. A probe of a refused `--servers` entry and of a failed embedding run showed `<masked-user>:<masked-password>`. The text of the engine, which names its endpoint with the masked userinfo, is outside this change.
- **Old files stay.** Saved reports and kept runs from before this change hold the URL as it was configured. The project keeps no backward compatibility before 1.0.0, so this change does not rewrite them. The pull request body tells a person who configured a password in a server URL to change it and to delete these files.

## Rejected alternatives

- **Replace `self.servers` with labels when the runner starts.** The client takes its endpoint from `self.servers`, and it needs the userinfo. A probe with a stubbed Ollama showed `Authorization: Basic` on each request. A label would send no authentication, and an Ollama behind a proxy would answer 401.
- **Mask the userinfo in the text with `mask_secrets`.** The text stays the data model and keeps the host, the path and the scheme. The origin gives only the host and the port, so no later reader can parse a secret out of it.
- **A new parser for the label.** `get_url_origin` and `origin_label` already read the URL as httpx2 sends it. #1107 and #1112 move every read of an address to the sending client's parser.
- **Refuse userinfo in the settings.** It breaks working Basic authentication. #1000 owns the validation of URL settings.
- **The scheme in the label (`http://example.com:11434`).** It does not match the text of the replies and the ledger, which show `host[:port]`.

## Non-goals

- The chat benchmark names a model by its `--models` entry, which can be `model@endpoint` with a password. #2643 changes it.
- The text of an embedding engine error names its endpoint with masked userinfo. The password is not in it.
