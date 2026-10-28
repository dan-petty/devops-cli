# k8s-service-proxy Specification

## Purpose
Authenticates requests through the Kubernetes API server proxy to cluster services using client credentials and token refresh hooks.

## Requirements

### Requirement: Proxy authentication uses client configuration auth settings
The service proxy SHALL extract authorization headers per request from the Kubernetes client configuration auth settings. When `refresh_api_key_hook` is set on the configuration, the proxy SHALL execute it before reading the authentication settings.

#### Scenario: Bearer token configuration sets Authorization header
- **WHEN** the Kubernetes client configuration contains a token under `BearerToken` or `authorization`
- **THEN** the proxied request carries the `Authorization` header with the bearer prefix and does not carry a `BearerToken` header

#### Scenario: Refresh hook rotates token
- **WHEN** the Kubernetes client configuration specifies a `refresh_api_key_hook`
- **THEN** the hook executes before the request and the updated token is transmitted in the `Authorization` header

#### Scenario: Client certificate authentication preserves mutual TLS
- **WHEN** the Kubernetes client configuration specifies client certificate files without an API key
- **THEN** the proxy target TLS context loads the certificate chain and no `Authorization` header is attached

### Requirement: A direct service URL looks up its host one time for each request
A request of `get_json` to a direct URL, not a `k8s://` address, SHALL resolve the host one time, at the connect, at the private level, and SHALL make no lookup before it.

#### Scenario: One request to a direct URL
- **WHEN** `get_json("http://example.com:9090", "api/v1/query")` runs
- **THEN** `example.com` is looked up one time, and the socket gets the address of that lookup
