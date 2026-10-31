## ADDED Requirements

### Requirement: Connect-time checking replaces pre-flight resolution
Every HTTP client in `src/devops_cli/` SHALL be checked at the connect through `devops_cli.http.client.new_http_client` or `new_async_http_client`. Pre-flight address resolution paths in `core/validation.py` SHALL be deleted.

#### Scenario: No pre-flight resolve paths remain
- **WHEN** the codebase is searched for `_resolve_host_ips` or `_enforce_non_private_ssrf`
- **THEN** no occurrences are found in `src/`

#### Scenario: No raw httpx2 client construction outside factory
- **WHEN** `src/` is searched for `httpx2.Client` or `httpx2.AsyncClient`
- **THEN** matches occur only in `src/devops_cli/http/client.py`

### Requirement: Kept pre-flight checks call vet_addresses
Callers that do not dial through an httpx2 client or that dial nothing SHALL validate host addresses using `devops_cli.http.egress.vet_addresses` at their egress level and document their time-of-check gap in a docstring.

#### Scenario: Qdrant client validates with vet_addresses
- **WHEN** `QdrantClient` is constructed with a non-service URL
- **THEN** it validates host addresses through `vet_addresses` at its configured level

#### Scenario: Kubernetes manifest URL validates with vet_addresses
- **WHEN** `devops k8s apply` receives an HTTP or HTTPS manifest URL
- **THEN** it validates host addresses through `vet_addresses` at the public level

#### Scenario: Docker engine endpoint validates with vet_addresses
- **WHEN** a TCP Docker daemon endpoint is parsed
- **THEN** it validates host addresses through `vet_addresses` at the public or private level according to `ai.allow_private_network`

### Requirement: Config init wizard admits loopback at configured level
The `devops config init` wizard SHALL check typed service URLs at `configured` level.

#### Scenario: Config init wizard allows loopback URL without flag
- **WHEN** a user enters a loopback URL in the config init wizard and `ai.allow_private_network` is false
- **THEN** the URL is accepted without error
