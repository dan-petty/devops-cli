# ai-reply-server Specification

## Purpose
How devops-cli names the server of an AI request. The name shows in the terminal output, the spend ledger, the metric labels, the spans and the response cache. It comes from the origin of the URL that the client called, so the userinfo of a configured URL never gets into these records.

## Requirements

### Requirement: A reply names its server by the origin of the URL that the client called
A reply that a provider endpoint sent SHALL carry the httpx2 origin of the URL that the client called. Its `backend_info` SHALL be `<provider> (<host[:port]>)`. The `host[:port]` text SHALL be the authority that httpx2 writes for that origin. Thus the host is in lower case, an IDN host is its A-label, and the text has no default port of the scheme.

#### Scenario: A reply from an Ollama URL
- **WHEN** `ai.ollama_urls` is `["http://example.com:11434"]` and the client sends a chat call
- **THEN** the origin of the reply has the scheme `http`, the host `example.com` and the port 11434
- **AND** the `backend_info` of the reply is `ollama (example.com:11434)`

### Requirement: The display, the ledger and the counters use the server text of the origin
The `backend_info` of the client SHALL use the `host[:port]` text of the origin of each configured URL, joined with ", " for several Ollama URLs. The spend ledger `server` and the `server` label of the AI counters SHALL be the same `host[:port]` text.

#### Scenario: An Ollama URL with an upper-case host
- **WHEN** `ai.ollama_urls` is `["http://Example.COM:11434"]` and the client sends a chat call
- **THEN** the `backend_info` of the client and of the reply is `ollama (example.com:11434)`
- **AND** the ledger `server` and the counter `server` label are `example.com:11434`

#### Scenario: An Ollama URL with the default port of its scheme
- **WHEN** `ai.ollama_urls` is `["http://example.com:80"]` and the client sends a chat call
- **THEN** the `backend_info` of the reply is `ollama (example.com)`
- **AND** the ledger `server` and the counter `server` label are `example.com`

#### Scenario: An Ollama URL with an IPv6 host
- **WHEN** `ai.ollama_urls` is `["http://[2001:db8::1]:11434"]` and the client sends a chat call
- **THEN** the `backend_info` of the reply is `ollama ([2001:db8::1]:11434)`
- **AND** the ledger `server` is `[2001:db8::1]:11434`

### Requirement: The userinfo of a configured AI URL stays out of every record
When a configured AI URL holds userinfo, devops-cli SHALL send it to the server as Basic authentication. devops-cli SHALL keep the userinfo out of `backend_info`, the spend ledger and the counter labels. It SHALL also keep the userinfo out of the span attributes, the span events and the response cache. These rules apply to a chat call, a streamed call and an embedding request.

#### Scenario: An Ollama URL with a password
- **WHEN** `ai.ollama_urls` is `["http://user:pw@example.com:11434"]` and the client sends a chat call
- **THEN** the server gets `Authorization: Basic dXNlcjpwdw==`
- **AND** the `backend_info` is `ollama (example.com:11434)`
- **AND** no ledger row, counter label, span or response-cache entry holds `pw`

#### Scenario: A gateway URL with a password
- **WHEN** `ai.gateway_url` is `http://user:pw@example.com:4000/v1` and the client sends a chat call
- **THEN** the server gets `Authorization: Basic dXNlcjpwdw==`
- **AND** the `backend_info` is `gateway (example.com:4000)`
- **AND** no ledger row, counter label, span or response-cache entry holds `pw`

#### Scenario: A streamed call over two Ollama URLs
- **WHEN** `ai.ollama_urls` is `["http://user:pw@example.com:11434", "http://example.com:11435"]` and the client streams a reply from the first server
- **THEN** the `backend_info` of the client is `ollama (example.com:11434, example.com:11435)`
- **AND** the ledger `server` and the counter `server` label are `example.com:11434`
- **AND** the `ai.llm.stream` span has no `server.address` and no `server.port`

#### Scenario: An embedding request to an Ollama URL with a password
- **WHEN** `ai.ollama_urls` is `["http://user:pw@example.com:11434"]` and the embeddings engine sends a batch
- **THEN** the ledger row has the `server` `example.com:11434` and the `backend_info` `ollama (example.com:11434)`
- **AND** the `ai.rag.ollama_embed_batch` span has `server.address` `example.com` and `server.port` 11434

### Requirement: The inference spans name the server with its port
The `ai.llm.dispatch` span SHALL write `server.address` and `server.port` from the origin of the reply. When the URL has no port, `server.port` SHALL be the default port of the scheme. The `ai.llm.stream` span opens before the client leases a server. It SHALL write the two attributes only when exactly one origin is configured, and SHALL take them from that origin.

#### Scenario: The default Claude endpoint
- **WHEN** the provider is `claude` with no `ai.api_base_url` and the client sends a chat call
- **THEN** the `backend_info` of the reply is `claude (api.anthropic.com)`
- **AND** the `ai.llm.dispatch` span has `server.address` `api.anthropic.com` and `server.port` 443

#### Scenario: A reply from the second of two Ollama URLs
- **WHEN** `ai.ollama_urls` is `["http://example.com:11434", "http://example.com:11435"]`, the server on port 11434 refuses the connection and the client sends a chat call
- **THEN** the `ai.llm.dispatch` span has `server.address` `example.com` and `server.port` 11435

#### Scenario: A streamed call to one Ollama URL
- **WHEN** `ai.ollama_urls` is `["http://example.com:11435"]` and the client streams a reply
- **THEN** the `ai.llm.stream` span has `server.address` `example.com` and `server.port` 11435

### Requirement: A configured URL with no origin shows unknown
The `backend_host` of the client SHALL show `unknown` for a configured URL that has no httpx2 origin or that httpx2 cannot read. It SHALL never show the text of that URL.

#### Scenario: A base URL with no scheme
- **WHEN** a config that skips validation has the provider `openai` and the `ai.api_base_url` `example.com:4000`
- **THEN** the `backend_info` of the client is `openai (unknown)`

#### Scenario: A base URL that httpx2 cannot read
- **WHEN** a config that skips validation has the provider `openai` and the `ai.api_base_url` `http://[::1`
- **THEN** the `backend_info` of the client is `openai (unknown)`

### Requirement: A served_by display shows the server without userinfo
The table of `devops ai cost report --by backend` SHALL show the `host[:port]` of each stored served_by value. `devops review benchmark` SHALL show its host. Both displays SHALL read an absolute URL with httpx2 and a bare `host[:port]` with the shared URL-or-authority reader. Both SHALL show `unknown` for a value that neither reader accepts, and SHALL never show the stored text.

#### Scenario: A stored served_by URL with a password
- **WHEN** the ledger holds a gateway call whose served_by is `http://user:pw@example.com:11434`
- **THEN** the table of `devops ai cost report --by backend` shows the serving backend `example.com:11434`

#### Scenario: A stored bare authority
- **WHEN** the ledger holds a gateway call whose served_by is `example.com:11434`
- **THEN** the table of `devops ai cost report --by backend` shows the serving backend `example.com:11434`

#### Scenario: A stored value that names no server
- **WHEN** the ledger holds a gateway call whose served_by is `example.com:`
- **THEN** the table of `devops ai cost report --by backend` shows the serving backend `unknown`

#### Scenario: A bare authority with userinfo in the review benchmark
- **WHEN** the review benchmark labels the backend `u:pw@example.com:11434`
- **THEN** the label is `example.com`

### Requirement: A benchmark names each server by the host and port of its URL
`devops ai benchmark` and the embedding benchmark SHALL name each server by the `host[:port]` text of the httpx2 origin of its URL, as a reply does. The name SHALL show in the output and in every report field that holds a server. It SHALL also show in the saved report and in the setup of the kept run. The benchmark SHALL send the userinfo of the URL as Basic authentication and SHALL write it nowhere. A URL with no origin SHALL show as `unknown`.

#### Scenario: A dry run over two Ollama servers
- **WHEN** a dry run of the chat benchmark has the servers `http://user:pw@example.com:11434` and `http://example.com:11435`
- **THEN** the `Workers:` line is `Workers: 2 (example.com:11434, example.com:11435)`
- **AND** the `server` of each response, peer grade and server summary is `example.com:11434` or `example.com:11435`
- **AND** no output and no report field holds `pw`

#### Scenario: A run against a server with a password
- **WHEN** `devops ai benchmark --servers http://user:pw@example.com:11434` runs a task against that server
- **THEN** the server gets `Authorization: Basic dXNlcjpwdw==` on each request
- **AND** the saved report names the server `example.com:11434`
- **AND** the setup of the kept run lists `example.com:11434`
- **AND** no terminal output, saved file or kept run holds `pw`

#### Scenario: A failed embedding run on a server with a password
- **WHEN** the server `http://user:pw@example.com:11434` answers an embedding request with HTTP 500
- **THEN** the result is failed, and its `server` is `example.com:11434`
- **AND** the server got `Authorization: Basic dXNlcjpwdw==`
- **AND** no output, log line or saved report holds `pw`

#### Scenario: A server URL with no origin
- **WHEN** a benchmark runner gets the server `not-a-url`
- **THEN** the `server` of each result is `unknown`
- **AND** no output and no report field holds `not-a-url`

### Requirement: A benchmark names the endpoint of a model by its host and port
The chat benchmark SHALL name a `model@endpoint` entry `model@host[:port]` in the output and in every report field that holds a model. The embedding benchmark SHALL name the endpoint of the entry by `host[:port]` in the `server` of its results. The setup of the kept run SHALL list the same names. The benchmark SHALL send the userinfo of the endpoint as Basic authentication and SHALL write it nowhere.

#### Scenario: A chat benchmark model with a password in its endpoint
- **WHEN** `devops ai benchmark --models m@http://user:pw@example.com:11434` runs a task
- **THEN** the server gets `Authorization: Basic dXNlcjpwdw==` on each request
- **AND** the terminal output, `models_evaluated`, the `model` of each response and the leaderboard name the model `m@example.com:11434`
- **AND** the saved report and the `setup.models` of the kept run hold `m@example.com:11434`
- **AND** no terminal output, saved file or kept run holds `pw`

#### Scenario: An embedding benchmark with a password in the endpoint
- **WHEN** the embedding benchmark has the model `m@http://user:pw@example.com:11434` and a second server `http://example.com:11435`
- **THEN** the progress lines and the `server` of each result name `example.com:11434` or `example.com:11435`
- **AND** the `setup.models` of the kept run lists `m@example.com:11434`
- **AND** no output, saved report, kept run or log line holds `pw`

### Requirement: A benchmark error names a server by its host and port
An error text of the benchmark SHALL name a server URL by its `host[:port]`, or by `unknown` for a URL with no origin. This holds for a user name alone, such as a token, as for a password. A refused `--servers` entry SHALL be named by its position in the list and by its label.

#### Scenario: A refused server entry with a password
- **WHEN** `devops ai benchmark --servers http://example.com:11434,ftp://user:pw@example.com:2121` runs
- **THEN** the command exits 1 with the message `--servers entry 2 (example.com:2121) is not an http or https URL.`
- **AND** no benchmark starts and the output does not hold `pw`

#### Scenario: A refused server entry with a token and no scheme
- **WHEN** `devops ai benchmark --servers token@example.com:11434` runs
- **THEN** the command exits 1 with the message `--servers entry 1 (unknown) is not an http or https URL.`
- **AND** the output does not hold `token`

#### Scenario: An embedding endpoint that is not the gateway
- **WHEN** the provider is `gateway`, the `gateway_url` is `https://token@example.com:4000/v1` and the endpoint of a model is `http://token@example.com:11434`
- **THEN** the result is failed with an error that names `example.com:11434` and `example.com:4000`
- **AND** no output, log line or saved report holds `token`

### Requirement: An embedding error names its endpoint without userinfo
The embeddings engine SHALL name an endpoint as the URL without its userinfo. This holds in an error, in the `details` of the error and in a log line. It SHALL still send the request to the URL with the userinfo.

#### Scenario: A failed embedding run on a server with a user name alone
- **WHEN** the server `http://token@example.com:11434` answers an embedding request with HTTP 500
- **THEN** the server gets `Authorization: Basic dG9rZW46`
- **AND** the error is `Embedding model m produced no embeddings: http://example.com:11434/api/embed answered HTTP 500: ...`
- **AND** no output, log line or saved report holds `token`
