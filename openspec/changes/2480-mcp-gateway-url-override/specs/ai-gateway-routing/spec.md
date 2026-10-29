# Spec Delta

## ADDED Requirements

### Requirement: The MCP gateway tools publish no URL
The MCP tools `ai_gateway_status`, `ai_gateway_routes` and `ai_gateway_probe_backend` SHALL publish no gateway URL and no backend URL. `ai_gateway_status` and `ai_gateway_routes` SHALL publish only `provider`, and `ai_gateway_probe_backend` SHALL publish only `backend`. A call that gives a URL SHALL fail and send no request.

#### Scenario: The tool schemas
- **WHEN** an MCP client lists the tools
- **THEN** `ai_gateway_status` and `ai_gateway_routes` publish the parameter `provider` and no other, and `ai_gateway_probe_backend` publishes the parameter `backend` and no other

#### Scenario: A call that gives a URL
- **WHEN** a client calls `ai_gateway_probe_backend` with `backend_url` set to a loopback URL, or calls `ai_gateway_routes` or `ai_gateway_status` with `gateway_url` set to a public URL, and the AI API key is set
- **THEN** the call fails, the socket gets no dial to the host of that URL, and the AI API key is not on the wire

### Requirement: The MCP gateway tools dial the configured gateway at the configured level
Each of the three MCP gateway tools SHALL query the configured gateway or backend. It SHALL dial loopback and public addresses, and private addresses only when `ai.allow_private_network` is true.

#### Scenario: The configured gateway at the configured level
- **WHEN** `ai_gateway_status` runs, and the host of `ai.gateway_url` answers `127.0.0.1` or `192.0.2.10`
- **THEN** the tool dials `127.0.0.1` whatever `ai.allow_private_network` says, and dials `192.0.2.10` only when `ai.allow_private_network` is true

### Requirement: The AI API key goes only to the configured gateway
`devops ai gateway routes` SHALL send the AI API key only to a gateway that has the scheme, host and port of the configured gateway URL. A `--gateway-url` of another origin, or any `--gateway-url` when no gateway is configured, SHALL get no AI API key. When such a gateway answers HTTP 401 or 403 and a key is set, the command SHALL fail with an error that says that the gateway got no key and names the origin of the gateway, and SHALL NOT ask for a key.

#### Scenario: The configured origin
- **WHEN** `--gateway-url` has the origin of `ai.gateway_url`, with the same path, another path or another spelling of the host
- **THEN** the request carries the AI API key

#### Scenario: Another origin
- **WHEN** `--gateway-url` has another host, another port or another scheme than `ai.gateway_url`, or holds the configured origin as user information of another host, or no gateway is configured
- **THEN** the request carries no AI API key

#### Scenario: Another gateway refuses the request
- **WHEN** a gateway of another origin answers HTTP 401 and the AI API key is set
- **THEN** the command fails with an error that says that this gateway got no key because the key goes only to the configured gateway, and the error holds the host and port of that gateway and no URL
