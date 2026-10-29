# ai-benchmark Specification

## Purpose
The servers that `devops ai benchmark` and its MCP tool `ai_benchmark` send requests to, and the part that a caller has in choosing them.

## Requirements

### Requirement: The MCP benchmark tool takes no server URL
The MCP tool `ai_benchmark` SHALL publish no `servers` parameter, and SHALL refuse a `models` entry of the form `model@url` before any command runs. It SHALL send its requests only to the servers of `ai.ollama_urls`, at the configured egress level. The command `devops ai benchmark` SHALL keep `--servers` and the `model@url` form. A person types them, so the command sends its requests to the servers that they name.

#### Scenario: The tool schema
- **WHEN** an MCP client lists the tools
- **THEN** `ai_benchmark` publishes the parameters `models`, `provider`, `benchmark_type`, `tasks_filter`, `concurrency`, `output`, `format_type`, `dry_run`, `explain`, `document`, `code` and `samples`, and no other

#### Scenario: A call that gives servers
- **WHEN** a client calls `ai_benchmark` with `servers` set to a loopback URL, and `ai.allow_private_network` is false
- **THEN** the call fails, the socket gets no dial to that host, and no request is written

#### Scenario: A call that gives a model endpoint
- **WHEN** a client calls `ai_benchmark` with a `models` entry `model@url` whose URL is a loopback URL, and `ai.allow_private_network` is false
- **THEN** the call fails with an error that names `models`, the socket gets no dial to that host, and no request is written

#### Scenario: The configured server
- **WHEN** a client calls `ai_benchmark` with plain model names, and `ai.ollama_urls` names one server
- **THEN** that server receives `POST /api/chat`, and no other host receives a request

#### Scenario: The configured level
- **WHEN** `ai_benchmark` runs, and the one configured server is `127.0.0.1` or `192.0.2.10`
- **THEN** the tool dials `127.0.0.1` whatever `ai.allow_private_network` says, and dials `192.0.2.10` only when `ai.allow_private_network` is true

#### Scenario: A person types the server
- **WHEN** a person runs `devops ai benchmark --servers http://example.com:11435 --models m1`, or `--models m1@http://example.com:11435`
- **THEN** the command sends its requests to `example.com:11435` and exits 0
