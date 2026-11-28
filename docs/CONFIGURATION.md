# DevOps CLI Configuration Reference

This document is automatically generated from `Settings` (`src/devops_cli/config/settings.py`).

DevOps CLI supports hierarchical configuration resolution through:
1. **CLI Flags & Arguments** (highest precedence)
2. **Environment Variables** (`DEVOPS_CLI_*`)
3. **Local Project Configuration** (the file `DEVOPS_CLI_CONFIG` names, else the nearest `config.yaml`, `.devcontainer/config.yaml`, `.devops/config.yaml`, `.devops.yaml` or `.devcontainer/.devops.yaml` from the working directory up to its repository root)
4. **Global User Configuration** (`~/.config/devops-cli/config.yaml`)
5. **System Defaults**

`setting_sources` in `src/devops_cli/config/settings.py` declares the order of items 2 to 5 one time, as pydantic-settings sources. A setting takes the value of the first source that holds it, and only that value is checked against the type of the setting: a value that a variable replaces is not checked. A null in the project file is no value, so the value of the global file stays. A config file whose document is not a mapping of keys to values stops the load with an error that names the file. A settings save writes a config file as YAML 1.2, and each read of a config file reads YAML 1.2 too. So a bare `off`, `on`, `yes`, `no` or `12:30` is a string, and only a bare `true` or `false` is a bool. A key that a mapping holds two times stops the load with an error that names the file, the line and the column. `DEVOPS_CLI_DATA_DIR` also moves each data path that no variable of its own sets into that directory, so the data paths of a config file do not apply. A credential resolves in its own order: the OS keyring, Vault, its variable, and last the config file, for a credential that a config file can hold.

A `devops review` command reads a tree it does not own. Started in a repository other than devops-cli's own, it looks for no project configuration, reading only the file `DEVOPS_CLI_CONFIG` names, and it resolves a relative data path under `~/.local/share/devops-cli` rather than under that repository, so its default data directory is `~/.local/share/devops-cli/.data`. What a review keeps -- its sessions, the feedback dataset, runs, samples, library contracts and AI spend -- every other command started outside devops-cli's own repository reads and writes there too. devops-cli's own repository is the one whose checkout holds the source of the devops-cli that runs, as an editable install's does; its code already runs, so a review started there, or in any worktree of it, reads its project configuration and keeps all data under its main worktree's `.data`, as every other command does. A clone nested in that checkout is another repository, and an installed devops-cli trusts no repository this way. An absolute `DEVOPS_CLI_DATA_DIR` or `data.dir` names the data directory every command uses.

A command that saves settings, such as `devops config set`, writes the file `DEVOPS_CLI_CONFIG` names, else the project configuration it finds, else the global one. It writes only the keys whose values the command changed, and it keeps the comments, the order of the keys and the keys that devops-cli does not know. A default, or a value that the other config file or an environment variable gives, stays out of the file, but `devops config set` writes the key that it names also when the value does not change. Before it changes the file, it copies the file to `<name>.bak-<YYYYMMDD-HHMMSS>` in the same directory, with the time in UTC, and keeps the newest 10 copies. Then it appends a record to the audit log (`data.audit_log_path`) with the command and the dotted names of the keys that changed, never a value. A save that changes no byte of the file writes nothing.

`devops config unset <key>` removes a key and its value from the same file, with the same copy and audit record. It edits the file and loads no settings, and `--dry-run` prints the change, with the lines of its unified diff and each credential as `***REDACTED***`, and writes nothing. The `ai` section and each section under it refuse a key that they do not declare. Such a key stops every command that loads the settings, with an error that names the full dotted key, its file and line, the release that removed the key when devops-cli knows it, and the `devops config unset` command that removes it.

To edit another file, run `DEVOPS_CLI_CONFIG=<file> devops config unset <key>`. `devops config audit-keys` names this command for each plaintext secret that it finds. Store a credential before you remove it: use `devops config set <key>`, with `--from-file <path>` for a multi-line one. The copy of the file, and each older copy, shows a credential that the command removes as `***REDACTED***`, so no copy holds its value.

`devops config set` takes a key that names a settings field with a value, or a credential. For any other key, it exits 1 with `Unknown config key: '<key>'` before it asks for a value or reads a file, and names the known keys with a similar name. `devops config get` gives the same message for a key that it cannot find.

`devops config set <key> --generate` makes the value of a credential that no person chooses, with the generator that the cluster Secret table declares for that credential, and stores it in the OS keyring. It prints the kind and the length of the value, and never the value. A value that the keyring already holds stays, and `--rotate` replaces it. `--dry-run` writes nothing. `devops k8s push-secrets` writes the cluster Secrets that read the stored values, and no other command writes them.

---

## GitHub Configuration (`github`)

GitHub authentication, default owner, and repository settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `default_org` | `Union` | - | `DEVOPS_CLI_GITHUB_DEFAULT_ORG` | Default GitHub organization |
| `template_repository` | `str` | `dan-petty/github-workflows` | `DEVOPS_CLI_GITHUB_TEMPLATE_REPOSITORY` | owner/name of the repository that holds the Copier template and the settings baseline that `devops repos onboard` applies |
| `release_app_client_id` | `Union` | - | `DEVOPS_CLI_GITHUB_RELEASE_APP_CLIENT_ID` | Client ID of the release App, which `devops repos onboard` writes to the variable RELEASE_APP_CLIENT_ID of the environment release |

## SSH Configuration (`ssh`)

SSH key generation, rotation, signing, and GitHub registration settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `key_dir` | `Path` | `~/.ssh` | `DEVOPS_CLI_SSH_KEY_DIR` | Directory for SSH key pairs |
| `key_prefix` | `Union` | - | `DEVOPS_CLI_SSH_KEY_PREFIX` | Prefix for generated SSH keys (defaults to devcontainer name or basename pwd) |
| `rotation_days` | `int` | `90` | `DEVOPS_CLI_SSH_ROTATION_DAYS` | SSH key rotation interval in days |

## Repositories Configuration (`repos`)

Multi-repository workspace discovery, cloning, and sync settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `base_dir` | `Path` | `repos` | `DEVOPS_CLI_REPOS_BASE_DIR` | Base directory for cloned repositories |

## Workspace Configuration (`workspace`)

Multi-root VS Code workspace file management and data tier settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `file` | `Path` | `.code-workspace` | `DEVOPS_CLI_WORKSPACE_FILE` | Path to VS Code workspace file |

## Grafana Configuration (`grafana`)

Grafana endpoint, authentication, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | `DEVOPS_CLI_GRAFANA_URL` | Grafana service URL |

## Prometheus Configuration (`prometheus`)

Prometheus query endpoint, authentication, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | `DEVOPS_CLI_PROMETHEUS_URL` | Prometheus service URL |

## Argo CD Configuration (`argocd`)

Argo CD server endpoint, authentication, TLS, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | `DEVOPS_CLI_ARGOCD_URL` | ArgoCD service URL |
| `github_app_id` | `Union` | - | `DEVOPS_CLI_ARGOCD_GITHUB_APP_ID` | ID of the GitHub App that Argo CD's GitHub notifier acts as |
| `github_app_installation_id` | `Union` | - | `DEVOPS_CLI_ARGOCD_GITHUB_APP_INSTALLATION_ID` | ID of the installation of Argo CD's notifier App on the managed repositories |
| `root_applications` | `list` | `['bootstrap', 'cluster']` | `DEVOPS_CLI_ARGOCD_ROOT_APPLICATIONS` | The Argo CD Applications that sync the other Applications (app of apps), the outer one first. A volume move pauses them before the Applications of the claim, and the last one is the Application that 'devops argo gitops watch' and 'sync' sync when no --app-name is given |

## Renovate Configuration (`renovate`)

The GitHub App that self-hosted Renovate acts as. `devops gh app-token --app renovate` reads these settings and the App's private key, the credential `renovate.github_app_private_key` (variable `DEVOPS_CLI_RENOVATE_GITHUB_APP_PRIVATE_KEY`, keyring entry `renovate_github_app_private_key`).

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `github_app_id` | `Union` | - | `DEVOPS_CLI_RENOVATE_GITHUB_APP_ID` | App ID or Client ID of the GitHub App that self-hosted Renovate acts as. GitHub takes either one as the issuer of the App's JWT |
| `github_app_installation_id` | `Union` | - | `DEVOPS_CLI_RENOVATE_GITHUB_APP_INSTALLATION_ID` | ID of the installation of the Renovate App on the Service repositories |

## Gitea Configuration (`gitea`)

gitea configuration settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `applications` | `list` | `['gitea', 'gitea-manifests']` | `DEVOPS_CLI_GITEA_APPLICATIONS` | The Argo CD Applications of the Gitea stack, which 'devops k8s doctor --stack gitea' checks |
| `url` | `Union` | - | `DEVOPS_CLI_GITEA_URL` | The HTTPS URL of the Gitea instance (with no path) |
| `username` | `Union` | - | `DEVOPS_CLI_GITEA_USERNAME` | The Gitea user login associated with gitea.token |
| `github_branches` | `list` | `['main']` | `DEVOPS_CLI_GITEA_GITHUB_BRANCHES` | The GitHub branch patterns mirrored to Gitea |
| `extra_checkouts` | `list` | `[]` | `DEVOPS_CLI_GITEA_EXTRA_CHECKOUTS` | Extra git checkouts outside repos/ carrying a gitea remote |
| `argocd_username` | `str` | `argocd` | `DEVOPS_CLI_GITEA_ARGOCD_USERNAME` | The Gitea user login that Argo CD uses to read repositories |

## Mattermost Configuration (`mattermost`)

mattermost configuration settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `team` | `str` | `homelab` | `DEVOPS_CLI_MATTERMOST_TEAM` | The Mattermost team that 'devops k8s bootstrap-mattermost' makes or reuses when no --team is given |

## Qdrant Vector Store (`qdrant`)

The vector store that RAG searches query and indexing writes to.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | `DEVOPS_CLI_QDRANT_URL` | Qdrant vector database server URL |
| `collection_prefix` | `str` | `devops` | `DEVOPS_CLI_QDRANT_COLLECTION_PREFIX` | Prefix for Qdrant collection names |
| `api_key` | `Union` | - | `DEVOPS_CLI_QDRANT_API_KEY` | - |
| `timeout` | `float` | `300.0` | `DEVOPS_CLI_QDRANT_TIMEOUT` | Seconds each Qdrant request waits per attempt: RAG searches, and indexing's upserts and deletes, which share the client |

## Valkey Configuration (`valkey`)

Valkey caching endpoint, authentication, TLS, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | `valkey://localhost:6379/0` | `DEVOPS_CLI_VALKEY_URL` | The Valkey endpoint, such as `valkeys://example.com:6380/0`: the scheme, the host, the port and the database. The scheme `valkeys` connects over TLS and checks the certificate against the host. The scheme `valkey` connects in plaintext. The URL holds no password: `valkey.password` is in the OS keyring |
| `password` | `Union` | - | `DEVOPS_CLI_VALKEY_PASSWORD` | - |
| `username` | `Union` | - | `DEVOPS_CLI_VALKEY_USER` | The ACL user that a Valkey client sends, such as `sweep`, `brain`, `agent` or `metrics`; an empty value sends no user and keeps the default user |
| `timeout` | `float` | `2.0` | `DEVOPS_CLI_VALKEY_TIMEOUT` | Valkey network socket connection/read timeout in seconds; the shared cache of embeddings, threat intel and library symbols waits at most 0.25 s for a connection (default: 2.0) |
| `threat_intel_ttl` | `int` | `86400` | - | - |

## Shared Run Index (`runs`)

PostgreSQL connection settings for the shared AI run index.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `index_url` | `Union` | - | `DEVOPS_CLI_RUNS_INDEX_URL` | Valkey holding the run index shared by workstations (set by `devops ai runs connect`) |

## Loki Configuration (`loki`)

Grafana Loki log query endpoint and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | `DEVOPS_CLI_LOKI_URL` | Loki service endpoint that a log query dials; unset, a log query dials `http://localhost:3100`, but `devops roadmap review run` dials no default address and skips its Loki facts (#5481) |

## Tempo Configuration (`tempo`)

Grafana Tempo distributed tracing query endpoint and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | - | - |

## Pyroscope Configuration (`pyroscope`)

Grafana Pyroscope continuous profiling endpoint and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | - | - |

## Telemetry & Metrics (`telemetry`)

OpenTelemetry export and Logfire settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `enabled` | `bool` | `True` | `DEVOPS_CLI_TELEMETRY_ENABLED` | Export OpenTelemetry traces and metrics |
| `endpoint` | `Union` | - | `DEVOPS_CLI_TELEMETRY_ENDPOINT` | OpenTelemetry collector that traces and metrics go to; unset, `OTEL_EXPORTER_OTLP_ENDPOINT` names it, else `http://localhost:4318` |
| `capture_command_args` | `bool` | `False` | - | Record the arguments of each program that devops-cli runs in `process.command_args` on its subprocess span, each argument through the secret mask. Off by default: an argument can be a credential that the mask does not find |
| `capture_llm_content` | `bool` | `False` | `DEVOPS_CLI_TELEMETRY_CAPTURE_LLM_CONTENT` | Record LLM prompt and reply text in OpenTelemetry and Logfire telemetry spans. Off by default to prevent exposure of sensitive data |
| `usage_ledger` | `bool` | `True` | `DEVOPS_CLI_TELEMETRY_USAGE_LEDGER` | Add each usage error of the CLI, by kind and names and with no argument value, as one line to `usage-errors.jsonl` under the user data root |
| `logfire` | `bool` | `False` | - | - |

## Kubernetes Configuration (`k8s`)

Kubernetes context, ingress domain, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `context` | `str` | `minikube` | `DEVOPS_CLI_K8S_CONTEXT` | Active Kubernetes cluster context name (e.g. minikube, docker-desktop, kind-cluster, or cloud context) |
| `domain` | `Union` | - | `DEVOPS_CLI_K8S_DOMAIN` | Base domain name for homelab ingress routes and tunnel services (e.g. example.com) |
| `tunnel_host` | `Union` | - | `DEVOPS_CLI_K8S_TUNNEL_HOST` | Hostname of the Kubernetes API route through the Cloudflare tunnel, which 'devops k8s tunnel start' forwards to a local port (e.g. k8s.example.com) |
| `addressing` | `Union` | - | - | Default addressing mode for cluster services: nodeport, proxy, or fqdn. |

## Cloudflare Configuration (`cloudflare`)

Cloudflare API token and zone settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `domain` | `Union` | - | `DEVOPS_CLI_CLOUDFLARE_DOMAIN` | Root or zone domain name managed in Cloudflare (e.g. example.com) |
| `tunnel` | `Union` | - | `DEVOPS_CLI_CLOUDFLARE_TUNNEL` | Cloudflare tunnel name or identifier (e.g. homelab) |
| `account_id` | `Union` | - | `DEVOPS_CLI_CLOUDFLARE_ACCOUNT_ID` | Cloudflare Account ID |
| `zone_id` | `Union` | - | `DEVOPS_CLI_CLOUDFLARE_ZONE_ID` | Cloudflare Zone ID |
| `public_ip_bypass` | `Union` | - | `DEVOPS_CLI_CLOUDFLARE_PUBLIC_IP_BYPASS` | Homelab public IP address or CIDR block permitted to bypass Cloudflare Access authentication |
| `access` | `CloudflareAccessConfig` | `allowed_emails=[] bypass_ips=[] public_ip_bypass=None application_name='Homelab Ingress' allow_policy_name='Allow homelab authorized emails' bypass_policy_name='homelab-public-ip-bypass'` | - | Cloudflare Zero Trust Access application and policy configuration |

## Sandbox Configuration (`sandbox`)

Isolated container sandbox runtime, resource limits, and network policy settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `exclude_home_dir` | `bool` | `True` | `DEVOPS_CLI_SANDBOX_EXCLUDE_HOME_DIR` | Exclude user home directory entirely from sandbox access (/home/**/* and ~/**/*) |

## CI Gate Configuration (`ci`)

Limit on how many CPU-heavy `devops ci` gates run at once on one host.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `gate_slots` | `Union` | - | `DEVOPS_CLI_CI_GATE_SLOTS` | Number of CPU-heavy devops ci gates that run at once on this host (default: one for each 16 CPUs) |

## AI & LLM Configuration (`ai`)

AI code review, chat agents, RAG semantic search, and embeddings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `provider` | `str` | `ollama` | `DEVOPS_CLI_AI_PROVIDER` | AI provider (ollama | claude | copilot | openai) |
| `model` | `str` | `qwen3.8:27b` | `DEVOPS_CLI_AI_MODEL` | Default AI model name |
| `decision_model` | `str` | `` | `DEVOPS_CLI_AI_DECISION_MODEL` | The decision model of the registered decision points of the roadmap jobs (ADR 0020), such as `typesafe/jev-1.14`: a System One model that answers closed questions with a calibrated probability and writes no text. The gateway serves it by name. Empty means no decision model: no point sends a request, and a point with no rule does what the job did before the point. A model that writes text is refused |
| `api_key` | `Union` | - | `DEVOPS_CLI_AI_API_KEY` | - |
| `reference_model` | `str` | `gpt-4o` | `DEVOPS_CLI_AI_REFERENCE_MODEL` | Hosted chat model whose genai-prices price values the local chat tokens in the AI spend reports |
| `reference_embedding_model` | `str` | `text-embedding-3-small` | `DEVOPS_CLI_AI_REFERENCE_EMBEDDING_MODEL` | Hosted embedding model whose genai-prices price values the local embedding tokens in the AI spend reports |
| `reference_provider` | `str` | `openai` | `DEVOPS_CLI_AI_REFERENCE_PROVIDER` | Provider in genai-prices of the two reference models |
| `price_overrides` | `dict` | `{}` | - | Price of a model that genai-prices does not know, by model name. A price in the file `pricing_overrides.json` of the data directory wins over the price here for the same model |
| `hardware_cost_usd` | `float` | `0.0` | `DEVOPS_CLI_AI_HARDWARE_COST_USD` | Cost in USD of the local AI hardware, which `devops ai cost` compares with the savings |
| `reasoning_effort` | `Union` | - | `DEVOPS_CLI_AI_REASONING_EFFORT` | AI reasoning effort level (low | medium | high) |
| `supports_reasoning` | `bool` | `False` | - | - |
| `use_model_sampling` | `bool` | `False` | - | Leave sampling parameters to the model. When true, requests carry neither temperature, top_p nor seed. |
| `temperature` | `float` | `0.1` | - | - |
| `top_p` | `float` | `0.95` | - | - |
| `context_window` | `int` | `32768` | - | - |
| `num_ctx` | `Union` | - | - | - |
| `max_tokens` | `Union` | - | - | - |
| `ollama_urls` | `list` | `[]` | `DEVOPS_CLI_AI_OLLAMA_URLS` | Ollama service URLs (comma-separated) |
| `embedding_ollama_urls` | `list` | `['http://ollama-24gib-embed-gpu0.llm.svc.cluster.local:11434']` | `DEVOPS_CLI_AI_EMBEDDING_OLLAMA_URLS` | Ollama service URLs for direct embeddings (comma-separated) |
| `ollama_max_parallel` | `int` | `2` | `DEVOPS_CLI_AI_OLLAMA_MAX_PARALLEL` | Maximum parallel requests per Ollama host |
| `gateway_provider` | `str` | `litellm` | - | - |
| `gateway_url` | `Union` | - | `DEVOPS_CLI_AI_GATEWAY_URL` | AI gateway URL |
| `gateway_enabled` | `bool` | `False` | - | - |
| `gateway_concurrency` | `dict` | `{}` | - | - |
| `portkey_url` | `Union` | - | - | - |
| `api_base_url` | `Union` | - | `DEVOPS_CLI_AI_API_BASE_URL` | AI API base URL |
| `allow_private_network` | `bool` | `False` | `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK` | Permit private-IP network targets |
| `max_retries` | `int` | `4` | `DEVOPS_CLI_AI_MAX_RETRIES` | Maximum retry count for AI requests upon response validation failure. A call to the LLM gateway is also sent at most this many times again, and only when it did not reach the gateway, or when its stream failed before its first event: the gateway retries every other failure |
| `request_timeout_seconds` | `int` | `1200` | `DEVOPS_CLI_AI_REQUEST_TIMEOUT_SECONDS` | The seconds that one pydantic-ai call to a chat group of the LLM gateway may take: every send of the call and the read of its stream. A call past it raises ModelRequestTimeout and is not sent again. Keep it above the router timeout of the gateway, so the gateway can retry a stuck attempt or fall back first. The implement step uses `roadmap.implement.request_timeout_seconds` |
| `first_token_timeout_seconds` | `int` | `60` | `DEVOPS_CLI_AI_FIRST_TOKEN_TIMEOUT_SECONDS` | Maximum seconds a streamed gateway call waits for its first content event before closing the attempt and retrying (`ai.max_retries`). Must be smaller than `ai.request_timeout_seconds` |
| `timeout` | `Union` | - | - | Seconds each LLM request waits for the next data of its reply: a streamed reply, such as every OpenAI-compatible chat reply, can take longer in total. `ai.tasks.<task>.timeout` sets one task's. Unset, a request waits 3600 s, and a review's analysis requests 1200 s |
| `tasks` | `AITasksConfig` | `chat=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) metadata=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) analysis=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) verification=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) compose=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) embedding=AIEmbeddingTaskOverride(provider=None, model='qwen3-embedding:0.6b', reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) implement=AIImplementTaskOverride(provider=None, model='devops-coder', reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=128000, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) triage=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) intake=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) retitle=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) refine=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) refine_review=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) alternatives=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) consolidate=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) stage=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) stage_review=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) fix_plan=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) fix_plan_review=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) implement_split=AITaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=None, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) fix_checks=AIFixChecksTaskOverride(provider=None, model=None, reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=128000, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None) review=AIReviewTaskOverride(provider=None, model='openrouter/deepseek/deepseek-v4.1-flash-1017', reasoning_effort=None, supports_reasoning=None, use_model_sampling=None, temperature=None, top_p=None, context_window=256000, num_ctx=None, max_tokens=None, ollama_urls=None, ollama_max_parallel=None, api_base_url=None, max_retries=None, timeout=None)` | - | - |
| `rag` | `AIRAGConfig` | `enabled=True top_k=5 score_threshold=0.35 chunk_size=2400 chunk_overlap=240` | - | - |
| `cache` | `AICacheConfig` | `enabled=True ttl_seconds=604800 max_entries=1000 append_cache=False` | - | - |
| `task_name` | `Union` | - | - | - |

## Open WebUI Configuration (`open_webui`)

Open WebUI endpoint, authentication, and service addressing settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | - | - |

## Data Storage Tier (`data`)

Local artifact caches, review findings, session histories, and log paths.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `dir` | `Path` | `.data` | `DEVOPS_CLI_DATA_DIR` | Root data directory for local reviews, cache, logs, and artifacts (default: ./.data; outside devops-cli's own repository, ~/.local/share/devops-cli/.data for review data and a `devops review` command) |
| `analysis_dir` | `Path` | `.data/analysis` | `DEVOPS_CLI_DATA_ANALYSIS_DIR` | Storage directory for pre-analysis metadata JSON files |
| `reviews_dir` | `Path` | `.data/reviews` | `DEVOPS_CLI_DATA_REVIEWS_DIR` | Storage directory for review session finding reports and artifacts |
| `logs_dir` | `Path` | `.data/logs` | `DEVOPS_CLI_DATA_LOGS_DIR` | Storage directory for CLI execution and SIEM audit logs |
| `models_dir` | `Path` | `.data/models` | `DEVOPS_CLI_DATA_MODELS_DIR` | Storage directory for local model checkpoints and weights |
| `cache_dir` | `Path` | `.data/cache` | `DEVOPS_CLI_DATA_CACHE_DIR` | Storage directory for local response and retrieval cache |
| `benchmarks_dir` | `Path` | `.data/benchmarks` | `DEVOPS_CLI_DATA_BENCHMARKS_DIR` | Storage directory for benchmark test runs and embedding leaderboard reports |
| `rag_dir` | `Path` | `.data/rag` | `DEVOPS_CLI_DATA_RAG_DIR` | Storage directory for local vector embedding index cache and retrieval data |
| `samples_dir` | `Path` | `.data/samples` | `DEVOPS_CLI_DATA_SAMPLES_DIR` | Storage directory for open-source sample repositories fetched at their pinned commits |
| `runs_dir` | `Path` | `.data/runs` | `DEVOPS_CLI_DATA_RUNS_DIR` | Storage directory for benchmark and evaluation run records, the run store's source of truth |
| `tls_dir` | `Path` | `.data/tls` | `DEVOPS_CLI_DATA_TLS_DIR` | Storage directory for generated local CA and TLS certificates |
| `audit_log_path` | `Path` | `.data/logs/audit.jsonl` | `DEVOPS_CLI_DATA_AUDIT_LOG_PATH` | Path to structured audit JSONL log file |
| `feedback_dataset_path` | `Path` | `.data/feedback_dataset.jsonl` | `DEVOPS_CLI_DATA_FEEDBACK_DATASET_PATH` | Path to feedback fine-tuning dataset JSONL file |

## Service Configuration (`service`)

In-cluster webhook receiver and background job runner settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `repos` | `list` | `[]` | `DEVOPS_CLI_SERVICE_REPOS` | Target repository list for service mode |
| `github_app` | `GitHubAppConfig` | `app_id=None installation_id=None slug=None token_repository=None drift_check=False` | - | - |
| `poll_interval_seconds` | `int` | `151` | `DEVOPS_CLI_SERVICE_POLL_INTERVAL_SECONDS` | Periodic polling interval for service mode in seconds |
| `poll_interval_idle_seconds` | `int` | `600` | `DEVOPS_CLI_SERVICE_POLL_INTERVAL_IDLE_SECONDS` | Polling interval for a repository with no open issues and no open pull requests, in seconds; a webhook starts its update at once |
| `webhook_url` | `str` | `https://hooks.example.com/webhooks/github` | `DEVOPS_CLI_SERVICE_WEBHOOK_URL` | Public URL of the Service's GitHub webhook route, which onboarding compares with the repository hooks |
| `github_requests_per_hour` | `int` | `500` | `DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR` | The most GitHub requests the Service sends in one hour, not counting those that GitHub answers with 304, as GitHub does not count them against its rate limit; a request that the last hour has no room for waits. The alert RoadmapServiceGitHubRequestsHigh follows this limit |
| `model_call_concurrency` | `int` | `1` | `DEVOPS_CLI_SERVICE_MODEL_CALL_CONCURRENCY` | The most model calls the Service keeps in flight at once; a lane that waits does so in the Service, where no stall timer runs |
| `max_failed_rounds` | `int` | `6` | `DEVOPS_CLI_SERVICE_MAX_FAILED_ROUNDS` | How many rounds in a row a roadmap job may fail before the Service suspends it until its input changes or its retry time comes; the retry time is the last failed round plus the wait of its failure class |
| `lanes` | `dict` | `{}` | - | Lanes that each run more than one roadmap job, as a map of a lane name to the jobs (rows of the due table) that the lane runs, such as {model: [stage, refine]}. Each job that no lane names runs in a lane of its own, named after the job. The jobs of a lane run one after the other in the order of the due table; two lanes never wait for each other. The Service reads this setting when it starts, so a change needs a restart |

## Roadmap Configuration (`roadmap`)

roadmap configuration settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `alternatives` | `AlternativesConfig` | `interval_minutes=239 backlog_interval_minutes=None backlog_threshold=None limit=5 first_pass_limit=20 recheck_days=30 retry_days=3 inventory_paths=['k8s', 'tf', '.devcontainer', 'src/devops_cli/config/commands.py', 'src/devops_cli/roadmap/runner_tools.py', 'src/devops_cli/infra/ansible_facts.py'] references='plan' references_mcp_url=None` | - | - |
| `brain` | `RoadmapBrainConfig` | `digest='on'` | - | - |
| `stage` | `RoadmapStageConfig` | `interval_minutes=37 backlog_interval_minutes=None backlog_threshold=None filter=['status=ready'] limit=3 planned_limit=20 gate_returns=3 gate_return_extensions=1 verify_repair_rounds=2 verify_repair_rounds_ceiling=4 plan_defect_limit=3 max_requests=250 max_tool_calls=200 plan_calls_advised=30 plan_calls_notice=40 review_calls_advised=40 review_calls_notice=60 step_tokens=64000 toolset='extended' mcp=False jev_completeness=False jev_shadow=False jobs=1 time_budget_seconds=9000 github_requests_per_hour=1000 job=None job_deadline=None` | - | - |
| `implement` | `RoadmapImplementConfig` | `toolset='base' effort=['low', 'medium'] in_runner=False repair_rounds=3 max_requests=500 max_tool_calls=1500 tool_retries=5 model_resends=1 extension_calls=20 step_token_budget=8000000 step_token_ceiling=None item_token_budget=20000000 step_time_limit_seconds=5400 item_time_limit_seconds=12600 digest_clears_per_class=1 digest_clears_per_item=3 continuations_per_item=2 ladder={'edit': ['devops-coder'], 'repair': ['devops-coder']} request_timeout_seconds=1200 command_timeout_seconds=1800 deadline_stall_seconds=4200 deadline_extension_seconds=5400 deadline_ceiling_seconds=14400 mcp=False max_parallel_jobs=1` | - | - |
| `inbox` | `RoadmapInboxConfig` | `draft_days=7 wait_days=7` | - | - |
| `intake` | `RoadmapIntakeConfig` | `interval_minutes=29 backlog_interval_minutes=None backlog_threshold=None jev='off'` | - | - |
| `metrics` | `RoadmapMetricsConfig` | `interval_minutes=13` | - | - |
| `fix_plan` | `RoadmapFixPlanConfig` | `interval_minutes=53 backlog_interval_minutes=None backlog_threshold=None mode='plan' time_budget_seconds=3600 head_attempts=2 revisions=3` | - | - |
| `fix_conflict` | `RoadmapFixConflictConfig` | `interval_minutes=37 backlog_interval_minutes=None backlog_threshold=None tier1_mode='on' soft_cap_rounds=2 hard_cap_rounds=4` | - | - |
| `fix_checks` | `RoadmapFixChecksConfig` | `mode='plan' token_budget=16000000 max_wait_minutes=360` | - | - |
| `open` | `RoadmapOpenConfig` | `interval_minutes=7 backlog_interval_minutes=None backlog_threshold=None mode='plan'` | - | - |
| `review` | `RoadmapReviewConfig` | `toolset='base' mode='plan' rounds=3 token_budget=16000000 infra_wait_hours=6` | - | - |
| `project_review` | `RoadmapProjectReviewConfig` | `namespaces=['agents', 'argo-workflows', 'argocd', 'cert-manager', 'cloudflared', 'cnpg-system', 'devops', 'gitea', 'llm', 'logging', 'mattermost', 'mattermost-operator', 'monitoring', 'object-store', 'otel']` | - | - |
| `refine` | `RoadmapRefineConfig` | `interval_minutes=7 backlog_interval_minutes=None backlog_threshold=None` | - | - |
| `research` | `RoadmapResearchConfig` | `max_calls_per_run=20 answer_expiry_days=30` | - | - |
| `model_jobs` | `int` | `2` | `DEVOPS_CLI_ROADMAP_MODEL_JOBS` | The most model Jobs that run at once in the cluster, for every repository together: the implement, stage and fix-checks Jobs (#5027, ADR 0021 section 5). A fix-checks Job that finds no free place is created suspended, and the implement and stage rows leave its place free, so a fix Job goes before a new implement or stage Job. `roadmap.stage.jobs` and the one implement Job of each repository still hold inside this limit |
| `mcp` | `RoadmapMcpConfig` | `url=None timeout_seconds=30.0` | - | - |
| `skip_authors` | `list` | `['dan-petty-renovate[bot]']` | `DEVOPS_CLI_ROADMAP_SKIP_AUTHORS` | The logins of the bots whose issues no roadmap row takes, such as `dan-petty-renovate[bot]`, the bot of the Renovate App: its Dependency Dashboard is a tracking issue that Renovate writes again each run, no work item (#6038). Such an issue is no Item and no Candidate. A login matches only when it is equal, and an empty list skips no author |
| `stall` | `RoadmapStallConfig` | `hours=24` | - | - |
| `state` | `RoadmapStateConfig` | `url=None username=None` | - | - |
| `verdict_partial_score` | `float` | `0.5` | `DEVOPS_CLI_ROADMAP_VERDICT_PARTIAL_SCORE` | The score of the verdict needs fix in the verdict score of stage and implement that `devops roadmap eval grades` gives. Mergeable scores 1, and a discard of the work of the job scores 0 |
| `decisions` | `dict` | `{}` | `DEVOPS_CLI_ROADMAP_DECISIONS` | The mode of each decision point of the roadmap jobs (ADR 0020, #4847), by the name of the point, as a JSON object such as `{"stage.verify_screen": "shadow"}`. `off` runs nothing. `rule` runs the deterministic rule and guards without a cuts file and records any configured model answers without acting. `shadow` runs the resolver chain (guards, proven rule, then the model of `ai.decision_model`, then the current behavior), records its band and the real result, and changes nothing. `on` lets the band act once fitted cuts pass the fit bar. A point that is not in the mapping is off. A key that names no registered point stops the settings from loading. A point in `shadow` or in `on` needs a cuts file in the repository for its fitted cuts, and the load stops when the file is absent |

## Research Configuration (`research`)

research configuration settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `judge` | `ResearchJudgeConfig` | `record_limit=50 daily_token_limit=500000` | - | - |

## Firecrawl Configuration (`firecrawl`)

Firecrawl web search API authentication settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `api_key` | `Union` | - | `DEVOPS_CLI_FIRECRAWL_API_KEY` | - |

## Crawl4AI Configuration (`crawl4ai`)

Address of the Crawl4AI service that returns the text of a web page.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `url` | `Union` | - | `DEVOPS_CLI_CRAWL4AI_URL` | Address of the Crawl4AI service that returns the text of a web page, such as `http://crawl4ai.devops.svc.cluster.local:11235` in the cluster. It has no default |

## Web Search Configuration (`search`)

The providers that web search asks, in order, and the language of the search.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `providers` | `list` | `['searxng', 'duckduckgo', 'firecrawl']` | `DEVOPS_CLI_SEARCH_PROVIDERS` | The providers of web search, in the order that a search asks them: `searxng`, `duckduckgo` or `firecrawl`. A provider that is not configured is skipped: `searxng` without `search.searxng_url`, and `firecrawl` without its key. A search goes to the next provider when one fails or returns no hit, and the first provider with a hit answers |
| `language` | `str` | `en` | `DEVOPS_CLI_SEARCH_LANGUAGE` | The language of a web search, as the `Accept-Language` of its request |
| `searxng_url` | `Union` | - | `DEVOPS_CLI_SEARCH_SEARXNG_URL` | Address of the SearXNG service for web search, such as `http://searxng.devops.svc.cluster.local:8080` in the cluster, or `http://127.0.0.1:8080` on a workstation after `kubectl port-forward -n devops svc/searxng 8080:8080`. A cluster address needs `ai.allow_private_network`. It has no default, and `searxng` is skipped without it |

## Infra Repos (`infra`)

The infra repos that `devops infra` manages, each with its agent access level, and the bounds of a plan, a drain and a node restart.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `plan_max_age_hours` | `int` | `24` | `DEVOPS_CLI_INFRA_PLAN_MAX_AGE_HOURS` | The age in hours after which a plan of an infra repo is too old to apply |
| `drain_timeout_seconds` | `int` | `180` | `DEVOPS_CLI_INFRA_DRAIN_TIMEOUT_SECONDS` | The time in seconds that the drain of one node may take. A pod on the node with a longer grace period makes the bound its grace period and 60 s more |
| `node_ready_timeout_seconds` | `int` | `900` | `DEVOPS_CLI_INFRA_NODE_READY_TIMEOUT_SECONDS` | The longest time in seconds that `devops infra` waits for a node to be Ready again |
| `repos` | `list` | `[]` | - | The infra repos, each with operational keys only: `repo` (owner/name), `path`, `kube_context`, `ssh_key_prefix` and `agent_access` (`none`, `plan`, `safe` or `full`; `none` when absent). The facts of a repository are in its project profile, `.devops/project.toml`. `devops infra onboard` writes an entry |

## Content Store (`store`)

S3-compatible content store endpoint, public web base URL, and signing region.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `s3_endpoint` | `Union` | - | `DEVOPS_CLI_STORE_S3_ENDPOINT` | S3-compatible gateway endpoint URL for the content store |
| `web_base_url` | `Union` | - | `DEVOPS_CLI_STORE_WEB_BASE_URL` | Public web base URL serving web-visible store prefixes |
| `region` | `str` | `us-east-1` | `DEVOPS_CLI_STORE_REGION` | AWS SigV4 region for content store signing (default: us-east-1) |

## Tf Configuration (`tf`)

tf configuration settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `stacks` | `list` | `[]` | - | OpenTofu stacks and their agent access level (`plan` or `apply`) |
| `github_reader` | `TFGitHubReaderConfig` | `app_id=None installation_id=None` | - | - |

## Top-Level Settings

Top-level workstation and environment settings.

| Option | Type | Default | Environment Variable | Description |
|---|---|---|---|---|
| `domain` | `Union` | - | - | Default domain name for the environment or workstation |
