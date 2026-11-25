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

The embedding benchmark command SHALL default to the configured embedding model (`qwen3-embedding:0.6b` when using the `gateway` provider). When all requests in a benchmark run fail, the command SHALL exit non-zero and SHALL NOT save the benchmark run record. When the provider is `gateway`, `plan_ai_benchmark` for `embedding` SHALL plan `POST /v1/embeddings` on the configured gateway URL rather than Ollama `/api/embeddings`.

#### Scenario: Embedding benchmark model selection
- **WHEN** `devops ai benchmark --type embedding` runs without `--models`
- **THEN** candidate models default to the configured embedding model or gateway model `qwen3-embedding:0.6b`

#### Scenario: Embedding benchmark gateway dry run
- **WHEN** `devops ai benchmark --type embedding --dry-run` runs with `provider` set to `gateway`
- **THEN** the planned request targets `<gateway>/v1/embeddings` with `qwen3-embedding:0.6b` and does not plan `/api/embeddings`

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
Every HTTP client in `src/devops_cli/` SHALL be checked at the connect through `http_client` or `async_http_client` of `devops_cli.http.entry`. Pre-flight address resolution paths in `core/validation.py` SHALL be deleted.

#### Scenario: No pre-flight resolve paths remain
- **WHEN** the codebase is searched for `_resolve_host_ips` or `_enforce_non_private_ssrf`
- **THEN** no occurrences are found in `src/`

#### Scenario: No raw httpx2 client construction outside the entry point
- **WHEN** `src/` is searched for `httpx2.Client` or `httpx2.AsyncClient`
- **THEN** matches occur only in `src/devops_cli/http/entry.py`

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

### Requirement: The Loki address is a setting
The settings SHALL hold the Loki address as `loki.url`, unset by default. The key SHALL take a URL with the scheme `http` or `https`. It SHALL refuse any other scheme, such as `k8s`, with an error that names `loki.url`. The variable `DEVOPS_CLI_LOKI_URL` SHALL set it.

#### Scenario: A Loki address is set
- **WHEN** `devops config set loki.url http://example.com:3100` runs
- **THEN** the command exits 0 and the config file holds `loki.url` as `http://example.com:3100`

#### Scenario: A cluster address is refused
- **WHEN** `devops config set loki.url k8s://logging/loki:3100` runs
- **THEN** the command exits non-zero, the error names `loki.url`, and the config file does not change

#### Scenario: The variable sets the address
- **WHEN** `DEVOPS_CLI_LOKI_URL` is `http://example.com:3100` and the settings load
- **THEN** `loki.url` is `http://example.com:3100`

### Requirement: A URL error text never holds the configured URL
The reason text of `normalize_ollama_base_url`, the error text of `_parse_and_validate_scheme`, and each error message and log line of `QdrantClient` that holds an exception SHALL NOT hold the configured URL, its userinfo or its path. `QdrantClient` SHALL replace each URL in an exception text with the label of its server.

#### Scenario: An Ollama URL with no host
- **WHEN** `normalize_ollama_base_url` runs with `http:///prefix/secret`
- **THEN** the raised `InvalidURLError` text holds `missing host or authority` and holds neither `http:///prefix/secret` nor `prefix` nor `secret`

#### Scenario: A service URL with no hostname
- **WHEN** `_parse_and_validate_scheme` runs with `http:///prefix/secret`
- **THEN** the raised error text holds `missing valid hostname` and holds neither `http:///prefix/secret` nor `prefix` nor `secret`

#### Scenario: A Qdrant error text that holds the request URL
- **WHEN** a native call of `QdrantClient.list_collections` fails with an exception whose text holds `http://user:secret@example.com:6333/prefix/path`
- **THEN** the `QdrantClientError` text and the debug log line hold `example.com:6333` and hold no `user`, no `secret`, no `prefix`, no `path` and no `://`

### Requirement: A review dry run takes its model endpoint from the configuration
The dry-run plan of a review command SHALL get the target of each model request from the configured AI endpoint, by the resolver that the review run uses. The model request of a review SHALL use the `analysis` task settings. When the resolver names a setting that is not set, the plan target SHALL start with that setting as a placeholder, such as `<ai.gateway_url>`, and the dry run SHALL make zero requests. A plan target SHALL NOT hold a gateway, Ollama or loopback address that no setting gives.

#### Scenario: Gateway provider with no gateway URL
- **WHEN** `ai.provider` is `gateway`, `ai.gateway_url` is not set and `devops review path src --dry-run` runs
- **THEN** the command exits 0 and its plan has the request `POST <ai.gateway_url>/chat/completions`

#### Scenario: Gateway provider with a gateway URL
- **WHEN** `ai.provider` is `gateway` and `ai.gateway_url` is `https://gateway.example.com/v1`
- **THEN** the review path plan has the request `POST https://gateway.example.com/v1/chat/completions`

#### Scenario: Ollama provider with no Ollama URLs
- **WHEN** `ai.provider` is `ollama` and `ai.ollama_urls` is empty
- **THEN** the review path plan has the request `POST <ai.ollama_urls>/api/chat`, and the corpus generate plan has the request `POST <ai.ollama_urls>/api/embeddings`

#### Scenario: The analysis task names its own provider
- **WHEN** `ai.provider` is `ollama` and `ai.tasks.analysis` sets the provider `gateway` with the base URL `https://gateway.example.com/v1`
- **THEN** the review path plan has the request `POST https://gateway.example.com/v1/chat/completions`

### Requirement: Embedding URL setting
The AI configuration SHALL hold the setting `ai.embedding_ollama_urls`, whose default is the one-element list of `DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL`.

#### Scenario: No embedding URL is set
- **WHEN** no source sets `ai.embedding_ollama_urls`
- **THEN** the resolved embedding URL list is `[DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL]`.

#### Scenario: An operator sets one embedding URL
- **WHEN** `ai.embedding_ollama_urls` holds one URL
- **THEN** the resolved embedding URL list is that URL alone.

#### Scenario: An entry is no URL
- **WHEN** `ai.embedding_ollama_urls` holds an entry with no http or https scheme and host
- **THEN** the resolution raises a `ConfigurationError` that names the key `ai.embedding_ollama_urls`.

### Requirement: Embedding request reaches the embedding Service
The embedding engine MUST send a direct Ollama embedding request to a URL of `ai.embedding_ollama_urls` and MUST NOT send it to `ai.ollama_urls`.

#### Scenario: The chat URLs hold the default Service
- **WHEN** `ai.ollama_urls` holds `DEFAULT_OLLAMA_CLUSTER_URL` and `ai.provider` is `ollama`
- **THEN** the request goes to `DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL` and no request goes to `DEFAULT_OLLAMA_CLUSTER_URL`.

#### Scenario: The embedding setting is empty
- **WHEN** `ai.embedding_ollama_urls` is empty and `ai.ollama_urls` holds `DEFAULT_OLLAMA_CLUSTER_URL`
- **THEN** the engine raises `EmbeddingsError` and sends no request.

### Requirement: Configure URLs writes the embedding Service
`devops k8s configure-urls` SHALL write `DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL` into `ai.embedding_ollama_urls` when it detects a reachable address for the embedding Service, and SHALL keep the default Ollama Service only in `ai.ollama_urls`.

#### Scenario: Configure URLs against a cluster
- **WHEN** a person runs `devops k8s configure-urls --stack llm` for a cluster that answers for both Services
- **THEN** the written configuration holds the embedding Service as `ai.embedding_ollama_urls` and the default Ollama Service as `ai.ollama_urls`.

#### Scenario: The embedding Service answers nothing
- **WHEN** the cluster gives no reachable address for the embedding Service
- **THEN** the written configuration holds the default of `ai.embedding_ollama_urls` and the command reports the other configured keys.
