## Purpose

How devops-cli names the server of an AI request in terminal output, in the spend ledger, in metric labels, in spans and in the response cache. The name comes from the origin of the URL that the client called, so the userinfo of a configured URL never reaches these records.

## ADDED Requirements

### Requirement: A reply names its server by the origin of the URL that the client called
A reply that a provider endpoint sent SHALL carry the httpx2 origin of the URL that the client called. Its `backend_info` SHALL be `<provider> (<host[:port]>)`, where `host[:port]` is the authority that httpx2 writes for that origin: the host in lower case, an IDN host as its A-label, and no port when the port is the default port of the scheme.

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
When a configured AI URL holds userinfo, devops-cli SHALL send it to the server as Basic authentication. It SHALL keep the userinfo out of `backend_info`, the spend ledger, the counter labels, the span attributes and events, and the response cache, for a chat call, a streamed call and an embedding request.

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

### Requirement: The inference span names the server with its port
The `ai.llm.dispatch` span SHALL write `server.address` and `server.port` from the origin of the reply. When the URL has no port, `server.port` SHALL be the default port of the scheme. For a reply with no origin, the span SHALL use the configured origin when exactly one is configured, and SHALL write no `server.address` and no `server.port` otherwise.

#### Scenario: The default Claude endpoint
- **WHEN** the provider is `claude` with no `ai.api_base_url` and the client sends a chat call
- **THEN** the `backend_info` of the reply is `claude (api.anthropic.com)`
- **AND** the `ai.llm.dispatch` span has `server.address` `api.anthropic.com` and `server.port` 443

#### Scenario: A reply with no origin and one configured URL
- **WHEN** `ai.ollama_urls` is `["http://example.com:11434"]` and the provider returns a reply with no origin
- **THEN** the `ai.llm.dispatch` span has `server.address` `example.com` and `server.port` 11434

#### Scenario: A reply with no origin and two configured URLs
- **WHEN** `ai.ollama_urls` holds two URLs and the provider returns a reply with no origin
- **THEN** the `ai.llm.dispatch` span has no `server.address` and no `server.port`

### Requirement: A configured URL with no origin shows unknown
The `backend_host` of the client SHALL be `unknown` for a configured URL that has no httpx2 origin or that httpx2 cannot read, and SHALL never be the text of that URL.

#### Scenario: A base URL with no scheme
- **WHEN** a config that skips validation has the provider `openai` and the `ai.api_base_url` `example.com:4000`
- **THEN** the `backend_info` of the client is `openai (unknown)`

#### Scenario: A base URL that httpx2 cannot read
- **WHEN** a config that skips validation has the provider `openai` and the `ai.api_base_url` `http://[::1`
- **THEN** the `backend_info` of the client is `openai (unknown)`

### Requirement: A served_by display shows the server without userinfo
`devops ai cost report --by backend` SHALL show the `host[:port]` of each stored served_by value, and `devops review benchmark` SHALL show its host. Both SHALL read an absolute URL with httpx2 and a bare `host[:port]` with the shared URL-or-authority reader. Both SHALL show `unknown` for a value that neither reader accepts, and SHALL never show the stored text.

#### Scenario: A stored served_by URL with a password
- **WHEN** the ledger holds a gateway call whose served_by is `http://user:pw@example.com:11434`
- **THEN** `devops ai cost report --by backend` shows the serving backend `example.com:11434`

#### Scenario: A stored bare authority
- **WHEN** the ledger holds a gateway call whose served_by is `example.com:11434`
- **THEN** `devops ai cost report --by backend` shows the serving backend `example.com:11434`

#### Scenario: A stored value that names no server
- **WHEN** the ledger holds a gateway call whose served_by is `example.com:`
- **THEN** `devops ai cost report --by backend` shows the serving backend `unknown`

#### Scenario: A bare authority with userinfo in the review benchmark
- **WHEN** the review benchmark labels the backend `u:pw@example.com:11434`
- **THEN** the label is `example.com`
