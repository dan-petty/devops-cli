# configured-service-urls Specification

## Purpose
Ensures that every service client uses only configured URLs or connections that the CLI opened itself, and stops with an error naming the setting when no configuration exists.

## Requirements

### Requirement: AI callers use only configured endpoints

Every AI caller SHALL obtain its endpoint URL from the active configuration. If the configured provider has no endpoint configured, the caller SHALL stop with a configuration error that names the missing setting. An AI caller SHALL NOT fall back to an unconfigured localhost or loopback address.

#### Scenario: Ollama provider with no configured URLs
- **WHEN** `ai.provider` is `ollama` and `ai.ollama_urls` is empty
- **THEN** executing an AI command fails with an error naming `ai.ollama_urls`

#### Scenario: Gateway provider with no gateway URL
- **WHEN** `ai.provider` is `gateway` and `ai.gateway_url` is not set
- **THEN** executing an AI command fails with an error naming `ai.gateway_url`

### Requirement: Service clients refuse unconfigured endpoints

Service clients for Qdrant, Tempo, Pyroscope, and Vault SHALL connect only to configured endpoints or ports opened by CLI port forwards. When a required endpoint setting is not configured, the command SHALL exit non-zero with an error naming the missing configuration key.

#### Scenario: Qdrant client without configured URL
- **WHEN** `qdrant.url` is not set and `devops rag query "test"` runs
- **THEN** the command exits non-zero with an error naming `qdrant.url`

#### Scenario: Observability without configured Tempo URL
- **WHEN** `tempo.url` is not set and `devops telemetry waterfall <trace-id>` runs
- **THEN** the command exits non-zero with an error naming `tempo.url`

### Requirement: Embedding benchmark defaults to configured embedding model

The embedding benchmark command SHALL default to the configured embedding model for the active provider. When all requests in a benchmark run fail, the command SHALL exit non-zero and SHALL NOT save the benchmark run record.

#### Scenario: Embedding benchmark model selection
- **WHEN** `devops ai benchmark --type embedding` runs without `--models`
- **THEN** candidate models default to the configured embedding model or gateway alias `devops-embedding`

#### Scenario: Embedding benchmark failed run
- **WHEN** every request in an embedding benchmark fails
- **THEN** the command exits with exit code 1 and records no run in the benchmark store

### Requirement: Configured AI service clients dial at the configured level
The LLM gateway model query, the gateway health probe, the backend probe, the `devops ai gateway load` Prometheus query, the embeddings engine, the pydantic-ai Ollama model, the pydantic-ai provider base URL, the benchmark endpoints and the `--source` URL of `devops ai cost update-pricing` SHALL dial loopback and public addresses. They SHALL dial private addresses only when `ai.allow_private_network` is true.

#### Scenario: A configured client without the flag
- **WHEN** `ai.allow_private_network` is false, and the host of the gateway, Ollama, embeddings, Prometheus, benchmark or pricing source URL answers `127.0.0.1` and then `192.0.2.10`
- **THEN** the client dials `127.0.0.1` and refuses `192.0.2.10` with no dial

#### Scenario: A configured client with the flag
- **WHEN** `ai.allow_private_network` is true, and the host of one of these URLs answers `127.0.0.1` and then `192.0.2.10`
- **THEN** the client dials both addresses

#### Scenario: The pydantic-ai Ollama model on a private host
- **WHEN** `ai.allow_private_network` is false, and the host of `ai.ollama_urls` answers `192.0.2.10`
- **THEN** a request of the Ollama model of pydantic-ai is refused with no dial

### Requirement: The gateway connect probe dials private addresses
The probe of `devops ai gateway connect` SHALL dial loopback, public and private addresses, whatever `ai.allow_private_network` says.

#### Scenario: A gateway node on a private address
- **WHEN** the host of the gateway node answers `192.0.2.10`, and `ai.allow_private_network` is false
- **THEN** the probe dials `192.0.2.10`

### Requirement: The pricing registry and the documentation crawler dial only public addresses
The fetch of the default pricing registry and the documentation crawler SHALL dial only public addresses, whatever `ai.allow_private_network` says.

#### Scenario: A non-public answer
- **WHEN** the host of the crawled page or of the default pricing registry answers `127.0.0.1` or `192.0.2.10`, with or without `ai.allow_private_network`
- **THEN** the client refuses the address with no dial

### Requirement: AI service clients dial the address that they checked
Each AI service client of these requirements SHALL resolve the host one time, at the connect, and SHALL give the socket the address that it checked, never the host name. Each one SHALL refuse cloud metadata addresses.

#### Scenario: A host that answers differently at a later lookup
- **WHEN** the host of one of these URLs answers a public address at the first two lookups and `169.254.169.254` at each later lookup
- **THEN** the socket gets neither the host name nor `169.254.169.254`

### Requirement: The Grafana, Prometheus and Argo CD clients dial at the configured level
The `devops grafana`, `devops prometheus` and `devops argo cd apps` commands, the Argo CD fleet sync, the Argo CD GitOps sync, the rollout metric gate, and the Argo CD and Grafana token calls SHALL dial loopback and public addresses. They SHALL dial private addresses only when `ai.allow_private_network` is true.

#### Scenario: A configured client without the flag
- **WHEN** `ai.allow_private_network` is false, and the host of `grafana.url`, `prometheus.url` or `argocd.url` answers `127.0.0.1` and then `192.0.2.10`
- **THEN** the client dials `127.0.0.1` and refuses `192.0.2.10` with no dial

#### Scenario: A configured client with the flag
- **WHEN** `ai.allow_private_network` is true, and the host of one of these URLs answers `127.0.0.1` and then `192.0.2.10`
- **THEN** the client dials both addresses

### Requirement: A command that gets a refused address prints the refusal
A `devops grafana`, `devops prometheus` or `devops argo cd apps sync` command that gets an address that its level refuses SHALL print the refusal without a traceback. It SHALL exit with status 2, the status of `SSRF_BLOCKED`. `devops grafana dashboards sync` SHALL stop at the first refused file.

#### Scenario: A private Prometheus address without the flag
- **WHEN** `ai.allow_private_network` is false, the host of `prometheus.url` answers `192.0.2.10`, and `devops prometheus query up` runs
- **THEN** the command exits with status 2 and prints the refusal, with no dial

#### Scenario: A private Grafana address in the dashboard sync
- **WHEN** `ai.allow_private_network` is false, the host of `grafana.url` answers `192.0.2.10`, and `devops grafana dashboards sync` runs on a directory with two dashboard files
- **THEN** the command prints the refusal one time and exits with status 2, with no dial

### Requirement: A failed Argo CD token mint ends the command with its cause
A `devops argo cd apps` command that mints an Argo CD token before its request SHALL print a failed mint with its cause, without a traceback, and SHALL exit with status 1, the status of a failed credential step. A refused address is such a cause.

#### Scenario: A private Argo CD address in the token mint
- **WHEN** `ai.allow_private_network` is false, the host of `argocd.url` answers `192.0.2.10`, the Argo CD admin password is set, no Argo CD token is stored, and `devops argo cd apps list`, `sync` or `status` runs
- **THEN** the command exits with status 1 and prints the failed token mint with the refusal, with no dial

### Requirement: The Grafana, Prometheus and Argo CD clients dial the address that they checked
Each client that the requirement "The Grafana, Prometheus and Argo CD clients dial at the configured level" names SHALL resolve the host one time, at the connect, and SHALL give the socket the address that it checked, never the host name. Each one SHALL refuse cloud metadata addresses.

#### Scenario: A host that answers differently at a later lookup
- **WHEN** the host of `grafana.url`, `prometheus.url` or `argocd.url` answers a public address at the first lookup and `169.254.169.254` at each later lookup
- **THEN** the socket gets neither the host name nor `169.254.169.254`

### Requirement: A service URL that is not HTTP stops the command before a request
The `devops grafana`, `devops prometheus` and `devops argo cd apps` commands SHALL exit with status 1 and an error that names the setting, without a traceback, when `grafana.url`, `prometheus.url` or `argocd.url` does not have the `http` or `https` scheme and a host. They SHALL make no lookup and send no request, also no token mint.

#### Scenario: A k8s address in prometheus.url
- **WHEN** `prometheus.url` is `k8s://monitoring/prometheus-server:9090` and `devops prometheus query up` runs
- **THEN** the command exits with status 1, the error names `prometheus.url`, and no lookup or dial occurs

#### Scenario: A k8s address in argocd.url with the admin password
- **WHEN** `argocd.url` is `k8s://argocd/argocd-server:80`, the Argo CD admin password is set, no Argo CD token is stored, and `devops argo cd apps list`, `sync` or `status` runs
- **THEN** the command exits with status 1, the error names `argocd.url`, and no lookup or dial occurs

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

### Requirement: The embeddings engine stops on a missing Ollama URL
When `ai.provider` is `ollama` and no Ollama URL is configured (`ai.ollama_urls` is empty and `ai.api_base_url` is not set), the embeddings engine SHALL raise an `EmbeddingsError` that names `ai.ollama_urls`. It SHALL NOT raise a `ZeroDivisionError`.

#### Scenario: The Ollama provider with an empty URL list
- **WHEN** `ai.provider` is `ollama`, `ai.ollama_urls` is empty, `ai.api_base_url` is not set, and `embed_texts` gets one text
- **THEN** it raises an `EmbeddingsError` whose message names `ai.ollama_urls`, and it stores no vector in the cache
