# ai-prewarm Specification

## Purpose
The Ollama servers that `devops ai prewarm` and its MCP tool `ai_prewarm` send requests to, and the part that a caller has in choosing them.

## Requirements

### Requirement: The MCP prewarm tool publishes no URL
The MCP tool `ai_prewarm` SHALL publish no `url` parameter. It SHALL send its requests only to the servers of `ai.ollama_urls`, at the configured egress level. The command `devops ai prewarm` SHALL keep `--url`. A person types it, so the command sends its request to the server that it names.

#### Scenario: The tool schema
- **WHEN** an MCP client lists the tools
- **THEN** `ai_prewarm` publishes the parameters `model`, `keep_alive`, `all_nodes`, `evict`, `output_format` and `json_output`, and no other

#### Scenario: A call that gives a URL
- **WHEN** a client calls `ai_prewarm` with `url` set to a loopback URL, and `ai.allow_private_network` is false
- **THEN** the call fails, the socket gets no dial to that host, and no request is written

#### Scenario: The configured servers
- **WHEN** a client calls `ai_prewarm` with no `url`, and `ai.ollama_urls` names two servers
- **THEN** each server receives `POST /api/generate` with the model name and the keep-alive value

#### Scenario: The configured level
- **WHEN** `ai_prewarm` runs, and the one configured server is `127.0.0.1` or `192.0.2.10`
- **THEN** the tool dials `127.0.0.1` whatever `ai.allow_private_network` says, and dials `192.0.2.10` only when `ai.allow_private_network` is true

#### Scenario: A person types the URL
- **WHEN** a person runs `devops ai prewarm --url http://example.com:11434`
- **THEN** the command sends `POST /api/generate` to `example.com:11434` and exits 0

### Requirement: A prewarm reply names each server by host and port
The output of `devops ai prewarm` and `devops ai preload`, and the reply of the MCP tool `ai_prewarm`, SHALL name each Ollama server as `host[:port]`. They SHALL NOT show the URL text of `ai.ollama_urls`, with its user name, password, path or query. The `nodes` of the JSON and YAML output SHALL use that text as keys. Two URLs with one host and port SHALL show as one node that is ok only when both URLs are ok.

#### Scenario: A URL with a user name and a query value
- **WHEN** `ai.ollama_urls` holds `http://FAKE-2676-user@example.com:11434/?x=FAKE-2676-query` and a client calls `ai_prewarm`
- **THEN** the reply shows `example.com:11434` and shows neither `FAKE-2676-user` nor `FAKE-2676-query`

#### Scenario: The JSON nodes
- **WHEN** `devops ai prewarm --json` runs with that URL
- **THEN** `nodes` is `{"example.com:11434": true}`

#### Scenario: The preload command
- **WHEN** `devops ai preload` runs with that URL
- **THEN** the output shows `example.com:11434` and shows neither `FAKE-2676-user` nor `FAKE-2676-query`

#### Scenario: Two URLs of one server
- **WHEN** two URLs have one host and port, and one of them fails
- **THEN** `nodes` holds one key for that server, with the value false

### Requirement: The model label of the prewarm counter is bounded
The label `model` of `devops_cli_ai_prewarms_total` SHALL hold only the characters `A-Z`, `a-z`, `0-9`, `.`, `_`, `:`, `/` and `-`, and SHALL hold at most 128 characters. Each other character SHALL become `_`.

#### Scenario: A model name with symbols
- **WHEN** `devops ai prewarm --model 'my/model`@v2`.0!beta'` runs
- **THEN** the counter label `model` is `my/model__v2_.0_beta`

#### Scenario: A long model name
- **WHEN** the model name has 300 characters
- **THEN** the counter label `model` has 128 characters

#### Scenario: A normal model name
- **WHEN** the model is `gemma4:26b`
- **THEN** the counter label `model` is `gemma4:26b`
