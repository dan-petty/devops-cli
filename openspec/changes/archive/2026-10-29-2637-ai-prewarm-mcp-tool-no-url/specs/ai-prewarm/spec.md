# Spec Delta

## Purpose

The Ollama servers that `devops ai prewarm` and its MCP tool `ai_prewarm` send requests to, and the part that a caller has in choosing them.

## ADDED Requirements

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
