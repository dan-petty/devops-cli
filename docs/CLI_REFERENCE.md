# DevOps CLI Reference

The command groups of `devops` and their commands. The page of each group in `commands/` holds the full text of each command: its usage, its arguments and its options.

## Command Groups

| Command Group | Summary |
|---|---|
| [`devops repos`](commands/repos.md) | Clone, synchronize, and manage organization repositories. |
| [`devops ssh`](commands/ssh.md) | Generate, rotate, audit, and register Ed25519 SSH keypairs. |
| [`devops branches`](commands/branches.md) | Branch management and Jira workflows. |
| [`devops devcontainer`](commands/devcontainer.md) | Manage devcontainer configurations. |
| [`devops workspace`](commands/workspace.md) | Manage multi-root VS Code workspace files (.code-workspace). |
| [`devops install-tools`](commands/install-tools.md) | Install and manage DevOps tool binaries. |
| [`devops openspec`](commands/openspec.md) | Check the OpenSpec change folders, regenerate the agent skills and archive a change. |
| [`devops new`](commands/new.md) | Write the files of a new command or a new test in project form. |
| [`devops k8s`](commands/k8s.md) | Manage Kubernetes clusters, pods, services, and workloads. |
| [`devops kustomize`](commands/kustomize.md) | Kustomize build and apply operations. |
| [`devops docker`](commands/docker.md) | Docker image management. |
| [`devops grafana`](commands/grafana.md) | Grafana dashboard and alert management. |
| [`devops prometheus`](commands/prometheus.md) | Prometheus metrics querying and analysis. |
| [`devops argo`](commands/argo.md) | Argo CD, Workflows, and Rollouts management. |
| [`devops config`](commands/config.md) | Show, set, get, or initialize CLI configuration. |
| [`devops ci`](commands/ci.md) | Run tests, linting, formatting, and type-checks. A run that selects test, security or typecheck first waits for a free gate slot, so the gates of parallel agents take turns. ci.gate_slots sets how many run at once. |
| [`devops uv`](commands/uv.md) | uv dependency management proxies. |
| [`devops scan`](commands/scan.md) | Security scanner suite: Trivy, Gitleaks, Semgrep, Kubeconform. |
| [`devops ai`](commands/ai.md) | Configure, test, chat, analyze, and review codebases (Ollama, Claude, Copilot). |
| [`devops review`](commands/review.md) | AI-powered code review and security audits. |
| [`devops mcp`](commands/mcp.md) | FastMCP server and Model Context Protocol integrations. The tool ai_fetch_page reads a web page through the Crawl4AI service. On a workstation, run `kubectl port-forward -n devops svc/crawl4ai 11235:11235` and set crawl4ai.url to http://127.0.0.1:11235. The token comes from the credential store, never from a tool parameter. |
| [`devops docs`](commands/docs.md) | Generate and validate CLI and architecture documentation. |
| [`devops roadmap`](commands/roadmap.md) | Read and write the roadmap on GitHub, its source of truth: issues, their labels and milestones. |
| [`devops pr`](commands/pr.md) | GitHub Pull Request workflows and reviews. |
| [`devops gh`](commands/gh.md) | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
| [`devops tf`](commands/tf.md) | OpenTofu and Terraform Infrastructure-as-Code operations. |
| [`devops infra`](commands/infra.md) | Manage an infra repo: a git repository with an Ansible inventory, its playbooks and roles. The settings name each infra repo and its agent access level (infra.repos). |
| [`devops tls`](commands/tls.md) | Generate and manage homelab TLS certificates and CAs. |
| [`devops telemetry`](commands/telemetry.md) | OpenTelemetry tracing, metrics, and Tempo observability. |
| [`devops cloudflare`](commands/cloudflare.md) | Cloudflare Zero Trust tunnels and DNS management. |
| [`devops serve`](commands/serve.md) | FastAPI REST & OpenAPI Service Engine for remote automation, health probes, and metrics. |
| [`devops test`](commands/test.md) | Test suite orchestration, git-diff aware test selector, and load testing. |
| [`devops pipeline`](commands/pipeline.md) | Programmable containerized pipeline execution (Dagger). |
| [`devops vault`](commands/vault.md) | Enterprise HashiCorp Vault secret broker |
| [`devops valkey`](commands/valkey.md) | Valkey workstation caching and in-memory data store |
| [`devops sandbox`](commands/sandbox.md) | Isolated workload sandbox container lifecycle engine. |
| [`devops dashboard`](commands/dashboard.md) | Interactive terminal UI dashboard for workstation situational awareness. |
| [`devops tui`](commands/tui.md) | Interactive terminal UI dashboard (alias) |
| [`devops status`](commands/status.md) | Inspect published operational status of upstream platforms (GitHub, Cloudflare) |
| [`devops survey`](commands/survey.md) | Outward-facing capability and upstream maturity survey. |
| [`devops research`](commands/research.md) | Read what the project pins and watch the upstream of each pin. |
| [`devops format`](commands/format.md) | Automatically apply code formatting in-place (ruff format). |
| [`devops lint`](commands/lint.md) | Run static analysis checks and automatically apply fixes (ruff check --fix). |

## Command Matrix

| Command Group | Subcommand / Usage | Purpose & Features |
|---|---|---|
| [**repos**](commands/repos.md) | `devops repos clone-org [OPTIONS] <org>` | Clone all repos from a GitHub org into `repos/<org>/.`. |
|  | `devops repos clone [OPTIONS] <url>` | Clone an individual repository into `repos/<org>/<name>/.` (or `repos/_standalone/<name>/.`). |
|  | `devops repos list [OPTIONS]` | List all cloned repositories. |
|  | `devops repos update [OPTIONS]` | Fetch (and optionally pull) all tracking branches across repos. |
|  | `devops repos sync [OPTIONS]` | Fetch (and optionally pull) all tracking branches across repos. |
|  | `devops repos worktrees COMMAND [ARGS]...` | Clone, synchronize, and manage organization repositories. |
| [**ssh**](commands/ssh.md) | `devops ssh generate [OPTIONS]` | Generate a new Ed25519 SSH key with prefix and YYYYMMDD date suffix. |
|  | `devops ssh register [OPTIONS]` | Generate, rotate, audit, and register Ed25519 SSH keypairs. |
|  | `devops ssh rotate [OPTIONS]` | Rotate keys older than rotation_days (default 90). |
|  | `devops ssh list [OPTIONS]` | List the managed SSH keys of the project prefix with their age and rotation status. |
|  | `devops ssh audit [OPTIONS]` | List the managed SSH keys of the project prefix with their age and rotation status. |
|  | `devops ssh status [OPTIONS]` | Show the active SSH key and days until rotation. |
| [**branches**](commands/branches.md) | `devops branches update [OPTIONS]` | Fetch and pull tracking branches across all repos. |
|  | `devops branches sync [OPTIONS]` | Fetch and pull tracking branches across all repos. |
|  | `devops branches jira [OPTIONS] <ticket_id>` | Create a feature branch for a Jira ticket: feature/PROJ-123[-slug]. |
|  | `devops branches list [OPTIONS]` | List branches across all repos. |
|  | `devops branches clean [OPTIONS]` | Delete local branches merged into main/master. |
| [**devcontainer**](commands/devcontainer.md) | `devops devcontainer init [OPTIONS] <repo_path>` | Scaffold .devcontainer/ using the published DevOps CLI devcontainer image. |
|  | `devops devcontainer update [OPTIONS] <repo_path>` | Update the Python image version in an existing devcontainer.json. |
|  | `devops devcontainer validate [OPTIONS]` | Validate .devcontainer/devcontainer.json manifest syntax and configuration schema. |
|  | `devops devcontainer list [OPTIONS]` | List repos with their devcontainer status. |
|  | `devops devcontainer unlock-keyring [OPTIONS]` | Create or unlock the gnome-keyring login keyring that gh, git and devops store secrets in. |
|  | `devops devcontainer post-create [OPTIONS]` | Execute DevContainer post-create setup tasks (history, shell completions, config prep). |
|  | `devops devcontainer post-start [OPTIONS]` | Execute DevContainer post-start tasks (SSH keys, git defaults, kubeconfig, MCP sync). |
|  | `devops devcontainer run-lifecycle [OPTIONS]` | Run specified DevContainer lifecycle hook tasks natively in Python. |
|  | `devops devcontainer bootstrap-k8s [OPTIONS]` | Execute Minikube cluster startup in the background. |
| [**workspace**](commands/workspace.md) | `devops workspace add [OPTIONS] <repo_path>` | Add a folder to the VS Code workspace file. |
|  | `devops workspace remove [OPTIONS] <repo_path>` | Remove a folder from the VS Code workspace file. |
|  | `devops workspace generate [OPTIONS]` | Regenerate the workspace file from all repos in the repos directory. |
|  | `devops workspace open [OPTIONS]` | Open the workspace in VS Code. |
|  | `devops workspace clean [OPTIONS]` | Clean stale reviews, analysis, logs, traces, benchmarks and cache under the data directory. |
| [**install-tools**](commands/install-tools.md) | `devops install-tools status [OPTIONS]` | Show each tool's locked version and where its command is installed, without a request. |
| [**openspec**](commands/openspec.md) | `devops openspec check` | Run the OpenSpec gate: validate every change and archived change, check the committed skills against a regeneration, render the instructions every agent reads, and find a requirement that two changes rewrite. Exits 1 on any problem. |
|  | `devops openspec regenerate` | Rewrite the committed OpenSpec skills with `openspec update --force` under an isolated configuration, so no developer's own profile decides what is written. |
|  | `devops openspec archive [OPTIONS] <change>` | Archive a change with `openspec archive <change> --yes`, then run `openspec validate --all --strict`. Both runs use an isolated configuration with telemetry off. The command exits 1 when a run fails, or when the archive leaves the change folder in place or makes no archive folder. A failed archive skips the validation. With --dry-run, it lists the two commands and runs none. |
|  | `devops openspec new [OPTIONS] <issue>` | Create an OpenSpec change folder in project form for an issue. |
| [**new**](commands/new.md) | `devops new command [OPTIONS] <group> <name>` | Add a command to a group that exists: its function, its help and message entries, and a failing test. The command writes over no file and prints the steps that stay manual. The page of the group is docs/commands/\<group\>.md. |
|  | `devops new test [OPTIONS] <module>` | Write the test file of a module of src/devops_cli at its mirror path under tests, with the fixtures of the edges the module reaches. The command writes over no file. The page is docs/TESTING.md. |
| [**k8s**](commands/k8s.md) | `devops k8s contexts [OPTIONS]` | List kubeconfig contexts and mark the active one. |
|  | `devops k8s switch-context [OPTIONS] <name>` | Switch active kubeconfig context and ensure cluster is running. |
|  | `devops k8s status [OPTIONS]` | Show node and pod summary for the current context. |
|  | `devops k8s apply [OPTIONS] <path>` | Apply a Kubernetes manifest (delegates to kubectl). |
|  | `devops k8s render [OPTIONS] <path>` | Render Kubernetes manifest templates with domain and variables substituted. |
|  | `devops k8s logs [OPTIONS] <pod> <query_arg>` | Stream pod logs or execute LogQL queries across cluster log streams. |
|  | `devops k8s bootstrap [OPTIONS]` | Bootstrap homelab Kubernetes cluster with Minikube, Calico, and ingress. |
|  | `devops k8s bootstrap-openwebui [OPTIONS]` | Bootstrap or activate a local administrator account for Open-WebUI. |
|  | `devops k8s bootstrap-mattermost [OPTIONS]` | Bootstrap Mattermost teams, channels, webhooks, and slash commands in Kubernetes. |
|  | `devops k8s deploy-stack [OPTIONS]` | Deploy one stack (infra, llm, logging, devops, gitea, chat) or all of them to Kubernetes with Helm and Kustomize. |
|  | `devops k8s sync-secrets [OPTIONS]` | Copy chart-generated admin credentials (Argo CD, Grafana) from the cluster into the OS keyring. |
|  | `devops k8s push-secrets [OPTIONS]` | Write the cluster's Secrets from the OS keyring (workstation keyring → cluster, the reverse of sync-secrets). Adopts live values the keyring lacks, generates the ones nobody types, and never replaces a live value without --rotate. |
|  | `devops k8s run-job [OPTIONS] <args>` | Run a devops command as a Job in namespace devops, from the template of a CronJob with only its arguments changed, follow its log and exit with its exit code. |
|  | `devops k8s configure-urls [OPTIONS]` | Auto-detect Kubernetes stack URLs and update CLI config. |
|  | `devops k8s service-url [OPTIONS] <service>` | Show, or fetch from, a cluster service address that needs no port-forward. |
|  | `devops k8s port-forward [OPTIONS]` | Port-forward k8s monitoring / LLM stack services to localhost ports. |
|  | `devops k8s port-forward-status` | List active background Kubernetes port-forward daemons. |
|  | `devops k8s port-forward-stop [OPTIONS]` | Terminate active background Kubernetes port-forward daemons. |
|  | `devops k8s teardown-stack [OPTIONS]` | Uninstall the k8s infrastructure / LLM stack and delete namespaces. |
|  | `devops k8s rbac-audit [OPTIONS]` | Audit RBAC RoleBindings and ServiceAccounts for overprivileged access. |
|  | `devops k8s lint [OPTIONS] <target>` | Validate K8s manifests and Helm charts using Red Hat Kube-linter. |
|  | `devops k8s audit [OPTIONS]` | Sanitize active K8s/Minikube cluster resource health using Derailed Popeye. |
|  | `devops k8s check-deprecated [OPTIONS] <target>` | Scan manifests for deprecated/removed K8s API versions using Fairwinds Pluto. |
|  | `devops k8s image-pins [OPTIONS] <target>` | Render each Argo CD Application of the environment tree, or the kustomization folder
TARGET, and resolve each image it pins in its registry, as an anonymous client, without pulling
it: a HEAD request of its manifest, which Docker Hub does not count against the anonymous
allowance of the network's public address. A git source of another public repository is
fetched at its revision. Exits 1, before it resolves an image, when an image has no digest and
the latest tag or no tag, unless Image Updater moves it or --managed names its repository.
Exits 1 when a registry does not hold an image or refuses the read. The CI job `image-pins`
runs the check on a pull request that changes k8s/. |
|  | `devops k8s crawl4ai-check [OPTIONS]` | Check that the Crawl4AI service refuses internal targets. It sends each of five routes
(/md, /html, /screenshot, /pdf and /llm) to each of five internal targets (the metadata
address, localhost, the Kubernetes API, the service itself and the roadmap Service) with the
token of the keyring, through a local port-forward, and sends each route once without the
token. It also tries a connect to the metadata address and to a private ClusterIP from a
throwaway pod that carries the label of the service, so the NetworkPolicy applies to it.
Run it at each bump of the image digest. The token never appears in the output. Exits 1 when
a target is served, a request without the token is not refused, or the pod opens a
connection. |
|  | `devops k8s searxng-check [OPTIONS]` | Check the points of the SearXNG service that a bump of the image digest can change. It sends
six search requests with format=json through a local port-forward: one for each category of
the provider, a query that starts with ! and names an engine that is off, a query that starts
with !! (the redirect is recorded and never followed), and a category that no kept engine
serves. It judges the keys of each reply, the hits, and the engines that must stay off. It
also tries three connects from two throwaway pods, so the NetworkPolicy applies to them: a
pod that is not a client of the service to port 8080, and a pod with the label of the service
to the metadata address and to a private ClusterIP. Run it at each bump of the image digest.
Exits 1 when a row fails or a pod opens a connection. |
|  | `devops k8s create-tls-secret [OPTIONS] <secret_name>` | Create or update a kubernetes.io/tls secret from certificate and private key files. |
|  | `devops k8s enable-tls [OPTIONS]` | Generate Homelab certificates and apply TLS secrets across Kubernetes cluster namespaces. |
|  | `devops k8s validate [OPTIONS] <manifest_path>` | Validate Kubernetes YAML manifests against OpenAPI schemas using Kubeconform. |
|  | `devops k8s validate-policy [OPTIONS] <manifest_path>` | Validate Kubernetes manifests against Kyverno or OPA admission policies. |
|  | `devops k8s stream-logs [OPTIONS] <pod_query>` | Stream logs across multiple pods in parallel using Stern or kubectl. |
|  | `devops k8s diff-helm [OPTIONS] <release_name> <chart_path>` | Preview Kubernetes manifest diffs before executing a Helm upgrade. |
|  | `devops k8s chaos [OPTIONS] <experiment>` | Run resilience and chaos experiments against Kubernetes workloads. |
|  | `devops k8s pods [OPTIONS]` | List running pods with health status, restart counts, and age. |
|  | `devops k8s security-stream [OPTIONS]` | Stream runtime security anomaly events from Kubernetes Falco eBPF probes. |
|  | `devops k8s gpu-matrix [OPTIONS]` | Query traditional homelab GPU matrix and model service alias mappings. |
|  | `devops k8s doctor [OPTIONS]` | Diagnose Kubernetes cluster deployment health, correlate failures, and recommend remediations. |
|  | `devops k8s ollama COMMAND [ARGS]...` | Prune Ollama models that no tier serves from the cluster nodes. |
|  | `devops k8s tunnel COMMAND [ARGS]...` | Keep the local end of the Kubernetes API route at k8s.\<domain\> running: one 'cloudflared access tcp' forward, for the tunnel kubeconfig context off the home network. |
|  | `devops k8s volume COMMAND [ARGS]...` | Move a local-path claim to a volume on another node, and reclaim orphaned PersistentVolumes. |
| [**kustomize**](commands/kustomize.md) | `devops kustomize build [OPTIONS] <path>` | Build kustomize overlays (delegates to kustomize build). |
|  | `devops kustomize diff [OPTIONS] <path>` | Show a diff of pending changes (delegates to kubectl diff -k). |
|  | `devops kustomize apply [OPTIONS] <path>` | Apply a kustomization (delegates to kubectl apply -k). |
| [**docker**](commands/docker.md) | `devops docker images [OPTIONS]` | List local Docker images. |
|  | `devops docker build [OPTIONS] <context>` | Build a Docker image. |
|  | `devops docker push [OPTIONS] <image>` | Push a Docker image to a registry. |
|  | `devops docker prune [OPTIONS]` | Remove stopped containers, unused networks, dangling images and, with --volumes, unused volumes. |
|  | `devops docker stats [OPTIONS]` | Display live container CPU, memory, and network I/O statistics. |
|  | `devops docker cache [OPTIONS]` | Introspect BuildKit multi-stage layer cache occupancy, reuse, and reclaimable space. |
|  | `devops docker sandbox [OPTIONS] <command>` | Execute workload inside an isolated, disposable Docker container sandbox. |
|  | `devops docker sign [OPTIONS] <image>` | Sign a container image using Sigstore Cosign (keyless or keyed). |
|  | `devops docker verify [OPTIONS] <image>` | Verify container image signature or attestation using Sigstore Cosign. |
| [**grafana**](commands/grafana.md) | `devops grafana search [OPTIONS]` | Search Grafana dashboards and folders by query string. |
|  | `devops grafana datasources [OPTIONS]` | List configured datasources. |
|  | `devops grafana alerts [OPTIONS]` | List alert rules (Grafana 9+ unified alerting). |
|  | `devops grafana dashboards COMMAND [ARGS]...` | Grafana dashboard and alert management. |
| [**prometheus**](commands/prometheus.md) | `devops prometheus query [OPTIONS] <expr>` | Execute an instant PromQL query. |
|  | `devops prometheus query-range [OPTIONS] <expr>` | Execute a range PromQL query and summarise the result. |
|  | `devops prometheus analyze [OPTIONS] <expr>` | Detect anomalies and project the trend of a metric series, computed locally. |
|  | `devops prometheus rules [OPTIONS]` | List Prometheus recording and alerting rules. |
|  | `devops prometheus targets [OPTIONS]` | List active Prometheus scrape targets. |
| [**argo**](commands/argo.md) | `devops argo sync [OPTIONS] <name>` | Synchronize an ArgoCD application (or multi-cluster fleet when --fleet is passed). |
|  | `devops argo cd COMMAND [ARGS]...` | Argo CD, Workflows, and Rollouts management. |
|  | `devops argo workflows COMMAND [ARGS]...` | Argo CD, Workflows, and Rollouts management. |
|  | `devops argo rollouts COMMAND [ARGS]...` | Argo CD, Workflows, and Rollouts management. |
|  | `devops argo fleet COMMAND [ARGS]...` | Argo CD, Workflows, and Rollouts management. |
|  | `devops argo gitops COMMAND [ARGS]...` | Argo CD, Workflows, and Rollouts management. |
| [**config**](commands/config.md) | `devops config show [OPTIONS]` | Print every setting that a variable sets and every credential. A credential shows as set or not set, never its value. |
|  | `devops config get <key>` | Print a single configuration value. |
|  | `devops config set [OPTIONS] <key> <value>` | Set a configuration value. Credentials go to the OS keyring; omit VALUE to type one hidden. |
|  | `devops config unset <key>` | Remove a key from the config file, also a key that stops the settings from loading. |
|  | `devops config init [OPTIONS]` | Interactive first-time setup wizard. |
|  | `devops config env-vars [OPTIONS]` | Output environment variables available for devops-cli configuration. |
|  | `devops config env [OPTIONS]` | Output environment variables available for devops-cli configuration. |
|  | `devops config output [OPTIONS]` | Output environment variables available for devops-cli configuration. |
|  | `devops config auth-headless <key> <token>` | Load secret tokens into ephemeral memory for headless CI environments lacking DBus. |
|  | `devops config audit-stream <destination>` | Stream stored audit records to SIEM destination URL. |
|  | `devops config audit-keys [OPTIONS]` | Audit OS Keyring token health, backend status, and zero-plaintext secret compliance. The audit scans each config file that the settings merge: the global config file and the project config file. It also scans config.yaml and .devops/config.yaml in the current directory. Exits 0 only when the audit is compliant. Exits 1 when a config file holds a plaintext secret, or when a config file cannot be read or parsed, reporting it unaudited. The full report prints before the exit. The alert of a leak names two commands. `devops config set <key>` stores a credential in the keyring. Add `--from-file <path>` for a multi-line credential, such as a PEM key. `DEVOPS_CLI_CONFIG=<file> devops config unset <key>` removes the value from the file of the leak. |
| [**ci**](commands/ci.md) | `devops ci test [OPTIONS] <paths>` | Run the test suite, or only the tests covering the given source files. |
|  | `devops ci coverage [OPTIONS]` | Run pytest with parallel code coverage analysis over src/. |
|  | `devops ci lint [OPTIONS]` | Run ruff linter across the project, automatically applying fixes by default. |
|  | `devops ci format [OPTIONS]` | Format codebase with ruff format (or verify in check-only mode with --check). |
|  | `devops ci typecheck [OPTIONS]` | Run mypy static type-checker strictly targeting Python 3.14 over src/. |
|  | `devops ci audit [OPTIONS]` | Run uv audit and npm audit to check for known package vulnerabilities. |
|  | `devops ci security [OPTIONS]` | Run bandit static security analysis over src/ at low severity and over tests/ at --severity. |
|  | `devops ci actionlint [OPTIONS]` | Run actionlint to validate GitHub Actions workflows for syntax and schema errors. |
|  | `devops ci docs [OPTIONS]` | Verify (or update with --fix) that documentation is up to date with CLI commands and configuration. |
|  | `devops ci uv-check [OPTIONS]` | Run uv check for fast static type checking and project validation. |
|  | `devops ci lockfile [OPTIONS]` | Verify lockfile consistency and freshness via uv lock --check. |
|  | `devops ci build [OPTIONS]` | Build the wheel and the sdist via uv build. |
|  | `devops ci outdated [OPTIONS]` | Display outdated dependencies and packages via uv tree --outdated. |
|  | `devops ci devcontainer [OPTIONS]` | Validate devcontainer manifest configuration syntax. |
|  | `devops ci deps [OPTIONS]` | Validate dependency hygiene and imports via deptry. |
|  | `devops ci test-settings [OPTIONS]` | Verify test configuration settings and environment variables. |
|  | `devops ci maintain [OPTIONS]` | Run automated toolchain, dependency freshness, and lockfile maintenance checks. |
|  | `devops ci run [OPTIONS]` | Run full CI and return a single pass/fail status. |
|  | `devops ci mutate [OPTIONS] <paths>` | Mutation-test functions with mutmut and show each mutant no test killed; never a gate. |
|  | `devops ci job-time [OPTIONS]` | Fail when the last runs of a CI job took more than the limit on average. Reads the job time of the last completed push runs of a workflow on a branch from GitHub's Actions API. A job that passed, failed or timed out counts, whatever the run concluded. Fails too when fewer runs than asked for could be read. |
|  | `devops ci durations [OPTIONS]` | Write the mean seconds of each test module to tests/module_durations.json, from the JUnit reports of the test shards of the last push runs of a workflow on a branch. The split of the test shards weighs each module by these seconds. gh downloads the artifacts of each run. A run whose artifacts GitHub no longer holds is left out. |
|  | `devops ci fail-to-pass [OPTIONS]` | Replay added or modified tests against the merge-base tree to prove a defect fix's tests fail unpatched. A changed module under tests/gate/*_checks/ runs its gate row on the base and head trees: a case of that module that fails on base and passes on head proves the fix. |
| [**uv**](commands/uv.md) | `devops uv sync [OPTIONS]` | Sync project dependencies into the virtual environment. |
|  | `devops uv lock [OPTIONS]` | Regenerate the uv lockfile. |
|  | `devops uv python-install [OPTIONS]` | Install project Python version with uv. |
|  | `devops uv run [OPTIONS]` | Run an arbitrary command using `uv run`. |
| [**scan**](commands/scan.md) | `devops scan trivy [OPTIONS] <target>` | Run Aqua Trivy vulnerability, secret, and misconfiguration scan. |
|  | `devops scan secrets [OPTIONS] <target>` | Run Gitleaks secret pre-filter scan across workspace or targets. |
|  | `devops scan workflows [OPTIONS] <target>` | Audit GitHub Actions workflows with zizmor offline: template injection, unpinned actions
and excessive permissions fail it, and every other finding is shown. |
|  | `devops scan sast [OPTIONS] <target>` | Run static application security testing (SAST) via Semgrep. |
|  | `devops scan complexity [OPTIONS] <target>` | Run AST-based cyclomatic complexity analysis. |
|  | `devops scan sbom [OPTIONS] <target>` | Generate Software Bill of Materials (SBOM) using Trivy (#1439). |
|  | `devops scan aibom [OPTIONS] <target>` | Generate AI Bill of Materials (AIBOM) with model licenses and hardware estimates. |
|  | `devops scan fix [OPTIONS] <target>` | Remediate vulnerable dependencies via lockfile upgrades and optional git branch creation. |
|  | `devops scan injection [OPTIONS] <target>` | Scan target files for prompt-injection smuggling vectors and canary tokens. |
|  | `devops scan report [OPTIONS] <target>` | Run every registered scanner and report deduplicated, correlated findings. |
|  | `devops scan sarif [OPTIONS] <document>` | Ingest a SARIF document from any tool and report it in the unified taxonomy. |
|  | `devops scan alerts [OPTIONS]` | File one issue for each open Trivy-config code scanning alert group that has none. |
| [**ai**](commands/ai.md) | `devops ai config [OPTIONS]` | Show or update AI provider configuration. |
|  | `devops ai models [OPTIONS]` | List available models for the configured provider. |
|  | `devops ai preload [OPTIONS]` | Preload configured model into VRAM across all configured Ollama servers. |
|  | `devops ai test [OPTIONS]` | Send a test prompt to verify AI provider connectivity across configured servers. |
|  | `devops ai prewarm [OPTIONS]` | Prewarm local models into GPU VRAM or evict idle models across cluster nodes. |
|  | `devops ai agents [OPTIONS]` | Generate LLM/Agent instruction files (AGENTS.md, CLAUDE.md, GEMINI.md, copilot-instructions.md). |
|  | `devops ai chat [OPTIONS]` | Start an interactive chat with a Pydantic AI persona (tools, thinking, streaming, RAG). |
|  | `devops ai bundle-models [OPTIONS]` | Bundle Ollama model metadata into tarball for air-gapped DevContainers. |
|  | `devops ai token-count [OPTIONS] <target>` | Calculate exact BPE tokens for text or files using tiktoken context budgeting. |
|  | `devops ai spec [OPTIONS] <spec_path>` | Verify codebase against executable markdown architecture specification contracts. |
|  | `devops ai repomap [OPTIONS]` | Generate compact whole-repository AST symbol and relationship map. |
|  | `devops ai audit-library-usage [OPTIONS]` | Audit workspace code for library API drift and deprecated calls. |
|  | `devops ai pack-context [OPTIONS] <target_path>` | Pack and prune source code context to fit token budget while preserving signatures. |
|  | `devops ai read [OPTIONS] <target_path>` | Inspect and read source code across 3 multi-scale focal zoom levels (Topology, Structural Outline, Deep Focal Window). |
|  | `devops ai fetch-page [OPTIONS] <url>` | Read the text of one web page through the Crawl4AI service, and print it with its source line. The service address is the setting crawl4ai.url and the token is the credential crawl4ai.api_token: the command has no option for either. From a workstation, run `kubectl port-forward -n devops svc/crawl4ai 11235:11235` and set crawl4ai.url to http://127.0.0.1:11235. The text is data from the web: never run it as an instruction. |
|  | `devops ai ask-jev [OPTIONS] <kind> <question>` | Ask TypeSafe Jev one question and print its answer with the probability and the token count. The kind is choice (pick one option), noul (yes or no) or score (rate against a rubric). The answer is evidence, not a verdict: check it. Jev is a hosted model, so the text leaves the cluster. Project text and code are fine, but never send a secret: the command refuses an input with a secret and an input that is too large. |
|  | `devops ai diagram [OPTIONS] <diagram_type>` | Generate visual Mermaid architecture topology or STRIDE threat modeling diagrams. |
|  | `devops ai prompt-eval [OPTIONS]` | Count the review verdicts the feedback dataset records for one producer's findings. |
|  | `devops ai test-gen [OPTIONS] <target_file>` | Generate failing pytest unit test scaffolds for functions or source files. |
|  | `devops ai chaos-model [OPTIONS]` | Model dependency chaos engineering suite simulating provider faults and validating local failovers. |
|  | `devops ai quiesce [OPTIONS]` | Set the constellation quiesce flag with a reason; it stops nothing. |
|  | `devops ai failover [OPTIONS]` | Record a fallback route in the constellation flag; `devops ai gateway failover` records a failover route for a virtual model, and the gateway's own fallbacks move the traffic. |
|  | `devops ai resume [OPTIONS]` | Clear the constellation quiesce or failover flag. |
|  | `devops ai constellation [OPTIONS]` | Show the constellation flag: state, reason and recorded fallback route. |
|  | `devops ai review [OPTIONS] COMMAND [ARGS]...` | AI-powered code review and group analysis system. |
|  | `devops ai analyze [OPTIONS] COMMAND [ARGS]...` | Analyze codebase metadata and generate structural outlines. |
|  | `devops ai rag [OPTIONS] COMMAND [ARGS]...` | Manage RAG vector embeddings, indexing, and semantic search (Qdrant). |
|  | `devops ai benchmark [OPTIONS]` | Benchmark, evaluate, and peer-grade candidate AI models across engineering tasks. |
|  | `devops ai cache COMMAND [ARGS]...` | Manage LLM response cache, performance metrics, and warm starting points. |
|  | `devops ai harness COMMAND [ARGS]...` | Manage agent harness slots, sub-agent local offloading, and tiered synthesis. |
|  | `devops ai ingest COMMAND [ARGS]...` | Ingest library API contracts, type stubs, and documentation. |
|  | `devops ai ast COMMAND [ARGS]...` | Tree-Sitter multilingual AST concrete syntax tree parsing and code graph synthesis. |
|  | `devops ai gateway COMMAND [ARGS]...` | LLM Gateway and distributed inference mesh management. |
|  | `devops ai runs COMMAND [ARGS]...` | Benchmark and evaluation runs, kept in the data directory and shared through Valkey. |
|  | `devops ai cost [OPTIONS] COMMAND [ARGS]...` | Track approximate lifetime spend and manage model pricing. |
|  | `devops ai spend [OPTIONS] COMMAND [ARGS]...` | Alias for 'cost' command. |
|  | `devops ai research COMMAND [ARGS]...` | Epistemic research, information foraging, and relational codebase exploration. |
| [**review**](commands/review.md) | `devops review path [OPTIONS] <targets>` | Review source files directly (no git required). |
|  | `devops review branch [OPTIONS] <branch_name>` | Review a git branch diff. |
|  | `devops review pr [OPTIONS] <number>` | Review a GitHub pull request. |
|  | `devops review findings [OPTIONS] <session>` | Inspect structured findings for a review session. |
|  | `devops review verify [OPTIONS] <session>` | Record a person's verdict on a review finding or candidate. |
|  | `devops review intake [OPTIONS] <session>` | Hand the qualifying findings of a session on merged code to roadmap intake, one candidate for each finding. A finding that an issue already carries is left out. |
|  | `devops review stats [OPTIONS]` | Compute and display review accuracy statistics across saved sessions. |
|  | `devops review benchmark [OPTIONS] <targets>` | Review the same files several times and report median time, LLM calls, tokens and backend busy share per stage. |
|  | `devops review score [OPTIONS] <sessions>` | Score saved review sessions against a label file: precision, recall and stability, each with its n. |
|  | `devops review export-feedback [OPTIONS]` | Append review verdicts to the JSONL feedback dataset, which `devops ai prompt-eval` reads. |
|  | `devops review fetch-databases [OPTIONS] <path>` | Fetch the osv-scanner and Trivy databases that a review binds read-only. The sandbox of a review has no network, so this is the one step that fetches them. Run it again when a review reports a coverage gap that names it. |
|  | `devops review corpus COMMAND [ARGS]...` | AI-powered code review and security audits. |
|  | `devops review samples COMMAND [ARGS]...` | AI-powered code review and security audits. |
|  | `devops review templates COMMAND [ARGS]...` | AI-powered code review and security audits. |
|  | `devops review rules COMMAND [ARGS]...` | AI-powered code review and security audits. |
| [**mcp**](commands/mcp.md) | `devops mcp serve [OPTIONS]` | Launch FastMCP server to expose devops-cli tools to MCP clients. |
|  | `devops mcp tools` | List all registered FastMCP tools and descriptions. |
|  | `devops mcp export-schemas [OPTIONS]` | Export FastMCP tool JSON schemas and instructions for MCP clients. |
| [**docs**](commands/docs.md) | `devops docs generate [OPTIONS]` | Generate comprehensive Markdown or JSON documentation for all CLI commands and tools. |
|  | `devops docs check [OPTIONS]` | Check that the generated documentation is up to date with the codebase. |
|  | `devops docs site COMMAND [ARGS]...` | Generate and validate CLI and architecture documentation. |
| [**roadmap**](commands/roadmap.md) | `devops roadmap intake [OPTIONS]` | Turn each open issue with no priority label into a roadmap item, or file a new candidate: intake sets the labels, adds a reason comment and names a possible duplicate for a person to close. It writes nothing without --confirm. Details: docs/roadmap/intake.md. |
|  | `devops roadmap refine [OPTIONS]` | Refine roadmap items to Ready: investigate open questions with tools that read the code and the documentation, then write the design, tasks and acceptance criteria to GitHub. Without --confirm, refine prints its plan only. Details: docs/roadmap/refine.md. |
|  | `devops roadmap alternatives [OPTIONS]` | Check open items for an open, maintained tool or library that already covers their need. A check writes a body block and posts a comment for a first check or a changed result, and a person decides what the tool means for the item. Details: docs/roadmap/alternatives.md. |
|  | `devops roadmap retitle [OPTIONS]` | Shorten the title summary of open items that is over 60 characters, and correct a title type that the branch types do not list. The job keeps the type and the scope of a listed type. It writes fix(security) in place of the type security, with no model call, and comments once on another unlisted type. A Planned item takes the summary of its plan pull request title and needs no model call; another item gets one model call. The job leaves a title that a person changed after the last job comment. An item that the job leaves gets the mark retitle.skipped and one log line with the reason, and the job does not select it again until its title, body or plan pull request changes. Without --confirm, it prints the new titles and writes nothing. |
|  | `devops roadmap consolidate [OPTIONS]` | Propose groups of open items that share a root cause, and write the plan to a local file. A model proposes and then tries to refute each shortlist, code checks the answers, and nothing changes on GitHub. Details: docs/roadmap/consolidate.md. |
|  | `devops roadmap stage [OPTIONS]` | Make Ready items Staged: for each item, push a branch with its OpenSpec change in one commit and open a draft plan pull request. The Service marks the draft ready when its checks pass. Details: docs/roadmap/stage.md. |
|  | `devops roadmap run [OPTIONS]` | Run the roadmap jobs that are due, in order: metrics, then intake, refine and the alternatives check, and record each one's last success. Intake is due on an issue reopened or a new issue, and decides at most 5 candidates a run and keeps a record of those it left beside the schedule; refine is due every roadmap.refine.interval_minutes (17 by default), on a first run, and after an intake that placed a critical fix or a P0 item; retitle is due every 61 minutes and on a first run; the alternatives check is due every roadmap.alternatives.interval_minutes (719 by default) and on a first run, and checks at most roadmap.alternatives.first_pass_limit items while an item has no check, and roadmap.alternatives.limit items after. A row whose last round counted roadmap.\<row\>.backlog_threshold or more items in its queue is due every roadmap.\<row\>.backlog_interval_minutes. Without --confirm, or with --dry-run, prints the due list and runs nothing. |
|  | `devops roadmap implement [OPTIONS]` | Implement a Staged or Planned item in bounded steps: with --group, run one task group in a checkout; without it, run the job, which takes items, runs their steps, and marks the pull request ready. Details: docs/roadmap/implement.md. |
|  | `devops roadmap plan-check [OPTIONS] <pull_request>` | Check a plan pull request: the stage gates without a model, the token size of each task group, the title, the body, the `Semantic PR title` check and a base spec that moved since the plan. Details: docs/roadmap/plan-check.md. |
|  | `devops roadmap plan-recheck [OPTIONS]` | Check each change folder on the default branch again. Each folder gets one result: ok, rewrite, new-plan, delivered or cleanup, and each refusal names its gate. With --branch, list the refusals of each gate for the branch and the default branch, and mark each refusal that the branch adds as a case to review. A folder gets rewrite only when the mechanical rewrite of the plan fixes it. The command reads GitHub and git and calls no model. It writes no file unless you give --confirm. Details: docs/roadmap/plan-recheck.md. |
|  | `devops roadmap explain [OPTIONS] <item>` | Say, for one issue, whether the refine job, the stage job and the implement job take it. For each job the answer is yes, or no with the reason of the first rule that fails: the issue is closed or is no item, the filter, the rules of the job (the Status, the owner, the stop on record, the plan and the branch, and the setting roadmap.stage.planned_limit), and the limit of a run. For refine the reason is the wait of the item, such as a question for a person. The reasons are the texts of the 'Left out' list of stage --plan and implement --plan. The command reads GitHub and git, calls no model and writes nothing. It uses the filter and the limit that the Service uses for each job. A group over the step budget shows only when an earlier run recorded it. |
|  | `devops roadmap inbox [OPTIONS]` | List what waits for a person in each repository of service.repos, or in the one that --repo names. Each line has its number, its age and the step that clears it, and an old wait is marked. It reads GitHub, calls no model and writes nothing; details: docs/roadmap/inbox.md. |
|  | `devops roadmap onboard [OPTIONS]` | Check one repository against the roadmap prerequisites and create missing labels. Details: docs/roadmap/onboard.md. |
|  | `devops roadmap repair [OPTIONS]` | Find the items that a placeholder reply of a model stalled. A returned item goes back to Ready. A stub refine item loses its stub section and its refine block. An item that a person set or answered stays as it is. This command reads GitHub and calls no model. It writes only with --confirm. Details: docs/roadmap/repair.md. |
|  | `devops roadmap return [OPTIONS] <item>` | Return an item to New with an evidence comment, handing it back to refinement when it cannot be built as specified or needs a refactor beyond its scope. The item gets the label status/new in place of its other status/* label. |
|  | `devops roadmap claim [OPTIONS] <item>` | Claim an item for an agent or a person with the label owner/agent or owner/human. An item has one owner. A person can take an item from the Service. The jobs stage and implement take no item that an agent or a person claimed. |
|  | `devops roadmap release [OPTIONS] <item>` | Release an item: remove its owner/* label, whoever holds it. No job removes the claim of an agent or a person. |
|  | `devops roadmap registries [OPTIONS]` | List the registry and ratchet declarations of the test modules, each with its token, its kind, its target path and its source path:line. Report a declaration that is not a tuple of literals and a ratchet assertion that no declaration covers, and exit 1. |
|  | `devops roadmap eval COMMAND [ARGS]...` | Score the roadmap jobs. grades reads the live result lines of each job in Loki. Each other command runs a job's real code on committed cases with a chosen model. Each is on demand and no part of devops ci. |
|  | `devops roadmap review COMMAND [ARGS]...` | Review a version range or a period of a repository: the facts of the window, each with its source, its query and the time of its read. |
|  | `devops roadmap step COMMAND [ARGS]...` | Run one step of a roadmap job by hand, the same way the Service runs it. Each step has one purpose. Details: docs/roadmap/stage.md. |
| [**pr**](commands/pr.md) | `devops pr list [OPTIONS]` | List pull requests with base targeting and review status. |
|  | `devops pr view [OPTIONS] <number>` | View details of a pull request. |
|  | `devops pr checks [OPTIONS] <number>` | Check remote CI quality gate status on a pull request. |
|  | `devops pr evidence [OPTIONS] <number>` | Post the check results of a pull request as one comment: the head commit, a table of the checks with their conclusion and link, the fail-to-pass run of a fix, and the skipped checks. Every number comes from GitHub. A new head commit updates the comment. |
|  | `devops pr wait [OPTIONS] <number>` | Wait until the checks of a PR settle, then name every blocker of its merge. |
|  | `devops pr monitor [OPTIONS] <number>` | Wait until the checks of a PR settle, then name every blocker of its merge. |
|  | `devops pr edit [OPTIONS] <number>` | Edit pull request base branch, title, body, or milestone. |
|  | `devops pr describe [OPTIONS] <issue>` | Print the title and the body of the pull request that delivers an issue. The first line is the title, then a blank line, then the body. |
|  | `devops pr create [OPTIONS]` | Open a draft pull request, into the default branch unless --base names another. |
|  | `devops pr ready [OPTIONS] <number>` | Mark a draft pull request as ready for review once draft readiness allows it. |
|  | `devops pr diff [OPTIONS] <number>` | View diff of a pull request. |
|  | `devops pr close [OPTIONS] <number>` | Close a pull request. |
|  | `devops pr check-readiness [OPTIONS] <number>` | Validate PR merge readiness: conflicts, draft state, checks, review threads, grounding
and draft readiness. |
|  | `devops pr update [OPTIONS] <number>` | Merge the base branch into a pull request only when a required check failed on its head. |
|  | `devops pr hardening-report [OPTIONS]` | Audit merged defect pull requests for guardrail additions to declared hardening surfaces. |
|  | `devops pr threads COMMAND [ARGS]...` | GitHub Pull Request workflows and reviews. |
| [**gh**](commands/gh.md) | `devops gh api [OPTIONS] <endpoint>` | Execute a GitHub API request with quota-derived spacing, rate-limit backoff, and optional caching. |
|  | `devops gh rate-limit [OPTIONS]` | Display GitHub REST and GraphQL API rate limits, quotas, and reset countdowns. |
|  | `devops gh status [OPTIONS]` | Display GitHub published operational status, key components, and active incidents. |
|  | `devops gh metrics [OPTIONS]` | Display comprehensive project metrics including release frequency, PRs, commits, CI pass rates, milestones, and roadmap Items. |
|  | `devops gh label COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh milestones COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh project COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh views COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh pages COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh issue COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh run COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh branch-protection COMMAND [ARGS]...` | Manage classic branch protection policies; does not cover rulesets. |
|  | `devops gh secret COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
|  | `devops gh pr COMMAND [ARGS]...` | GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation. |
| [**tf**](commands/tf.md) | `devops tf init [OPTIONS] <directory>` | Initialize an OpenTofu working directory. |
|  | `devops tf plan [OPTIONS] <directory>` | Generate and show an OpenTofu execution plan. |
|  | `devops tf apply [OPTIONS] <directory>` | Create or update OpenTofu infrastructure. |
|  | `devops tf destroy [OPTIONS] <directory>` | Destroy OpenTofu-managed infrastructure. |
|  | `devops tf output [OPTIONS] <directory>` | Read an output variable from the OpenTofu state. |
|  | `devops tf validate [OPTIONS] <directory>` | Validate the OpenTofu configuration files in a directory. |
|  | `devops tf fmt [OPTIONS] <directory>` | Rewrites OpenTofu configuration files to canonical format. |
|  | `devops tf status <directory>` | Show OpenTofu directory state, initialization status, and provider plugins. |
|  | `devops tf graph [OPTIONS] <directory>` | Inspect the in-memory resource dependency graph and blast radius. |
|  | `devops tf drift [OPTIONS] <directory>` | Compare declared configuration against recorded state. |
|  | `devops tf deploy-cloud [OPTIONS]` | Deploy cloud Kubernetes infrastructure for AWS, Azure, or GCP. |
|  | `devops tf lint [OPTIONS] <directory>` | Run TFLint static analysis on Terraform/OpenTofu configurations. |
|  | `devops tf notify-plan [OPTIONS]` | Format an OpenTofu plan as a collapsible pull request comment and print it. The command sends no request. |
|  | `devops tf cost COMMAND [ARGS]...` | OpenTofu and Terraform Infrastructure-as-Code operations. |
| [**infra**](commands/infra.md) | `devops infra onboard [OPTIONS] <repo>` | Check an Ansible infra repo for what devops infra needs, and print one row for each check with its state and the next step. The check fetches origin and reads the head of the default branch, not the working tree of the checkout, with local tool output only. With --confirm, write the entry of the repo in infra.repos, at agent access none unless a person gives --agent-access. |
|  | `devops infra status [OPTIONS] <repo>` | Show each inventory host of an infra repo with the state of its Kubernetes node: Ready, cordoned, kernel, kubelet, memory capacity and allocatable memory, and GPUs. The hosts come from the head of the default branch at origin, and the nodes from the kube context of the entry. With --ping, also check SSH to each host in service and whether it waits for a reboot. |
|  | `devops infra plan [OPTIONS] <repo> <playbook>` | Run a playbook of an infra repo in check mode with diffs on its hosts in service, and show for each host the changed tasks, the disruptive changes (reboot, service-restart:\<unit\>, drain), the changes with the diff hidden and the tasks that check mode skipped. The run exports a commit that origin holds, by default the head of the default branch, never the working tree. It changes no host. The plan record and the runner artifacts stay in <data dir>/infra/\<owner\>/\<name\>/plans/\<id\>/. An agent needs the agent access level plan or above. |
|  | `devops infra apply [OPTIONS] <repo> <playbook>` | Apply a saved plan of devops infra plan to the hosts of an infra repo. The apply needs the plan id and the playbook, limit and tags of the plan, a plan not older than infra.plan_max_age_hours, a commit that origin holds and a healthy cluster. The hosts with no disruptive change run together. Each disruptive host runs alone in plan order: drain check, drain, a fresh check that must equal the plan, the run, Ready with the GPUs of before, the health of the nodes, uncordon only when the node was schedulable before, and no critical alert. The health checks leave out the nodes of the hosts out of service and each critical alert whose node label names one of them, and the report names each alert that they left out. The drain waits for the longest grace period of a pod of the node, and the apply names each workload that is down while the node is cordoned, because only that node can mount its volume. A change that the plan does not show, or the first failure, stops the apply. Each apply writes an audit record. An agent needs the agent access level safe for a plan with no disruptive change and no unchecked task, else full; an agent applies only a commit of the default branch, or at full the head of an open pull request, and only with host key checks on. An agent runs the command as one plain command: the project allow rule Bash(uv run devops *) lets it start, and the owner keeps that rule. A compound shell line (an assignment, ;, &&, |) goes to the auto-mode classifier. The agent access level of the repo is the real control. |
| [**tls**](commands/tls.md) | `devops tls ca [OPTIONS]` | Generate a self-signed Root Certificate Authority (CA) key pair. |
|  | `devops tls cert [OPTIONS]` | Generate an X.509 TLS certificate signed by local CA or self-signed. |
|  | `devops tls homelab [OPTIONS]` | Generate complete Homelab TLS bundle (Root CA, Wildcard + Stack Services Cert). |
|  | `devops tls inspect <cert_path>` | Inspect and display metadata of an X.509 certificate. |
|  | `devops tls verify [OPTIONS] <cert_path>` | Verify an X.509 certificate cryptographic chain against a CA certificate. |
|  | `devops tls enable-k8s [OPTIONS]` | Generate and apply TLS secrets (kubernetes.io/tls) across Kubernetes namespaces. |
| [**telemetry**](commands/telemetry.md) | `devops telemetry status [OPTIONS]` | Check OpenTelemetry collector health, Tempo endpoint, and trace propagation status. |
|  | `devops telemetry connect [OPTIONS]` | Find the cluster's OpenTelemetry collector, check it answers, and send telemetry there. |
|  | `devops telemetry logfire [OPTIONS]` | Display the status of the Logfire bridge. |
|  | `devops telemetry test [OPTIONS]` | Emit a test OpenTelemetry trace span and metric to the configured collector. |
|  | `devops telemetry profile [OPTIONS] <command>` | Run a devops-cli command, or name a trace, and show its span waterfall as Tempo recorded it. |
|  | `devops telemetry open-ui` | Print and show the Tempo HTTP API endpoint for inspecting traces. |
|  | `devops telemetry semconv COMMAND [ARGS]...` | The GenAI semantic conventions that LLM span attributes are checked against. |
| [**cloudflare**](commands/cloudflare.md) | `devops cloudflare status [OPTIONS]` | Verify Cloudflare API token authentication and inspect zone status. |
|  | `devops cloudflare service-status [OPTIONS]` | Display Cloudflare published operational status, key components, and active incidents. |
|  | `devops cloudflare dns COMMAND [ARGS]...` | Cloudflare Zero Trust tunnels and DNS management. |
|  | `devops cloudflare tunnel COMMAND [ARGS]...` | Cloudflare Zero Trust tunnels and DNS management. |
|  | `devops cloudflare access COMMAND [ARGS]...` | Cloudflare Zero Trust tunnels and DNS management. |
| [**serve**](commands/serve.md) | `devops serve [OPTIONS]` | FastAPI REST & OpenAPI Service Engine for remote automation, health probes, and metrics. |
| [**test**](commands/test.md) | `devops test run [OPTIONS] <target>` | Execute pytest test suite with optional git-diff aware test selection. |
|  | `devops test load [OPTIONS] <script_path>` | Execute developer-centric load, spike, and latency tests against services using k6. |
|  | `devops test sandbox [OPTIONS] <command>` | Execute test command inside an isolated, disposable Docker container sandbox. |
|  | `devops test profile-memory [OPTIONS] <target>` | Deterministic async memory and connection pool profiler using tracemalloc. |
| [**pipeline**](commands/pipeline.md) | `devops pipeline [OPTIONS] <pipeline_path>` | Execute reproducible, containerized developer pipelines with Dagger. |
| [**vault**](commands/vault.md) | `devops vault status [OPTIONS]` | Inspect HashiCorp Vault cluster health and initialization status. |
|  | `devops vault get [OPTIONS] <path>` | Fetch a secret from Vault, or from the OS keyring when Vault cannot answer. |
|  | `devops vault set [OPTIONS] <path> <key_values>` | Store secret key-value pairs in HashiCorp Vault KV-v2 engine. |
|  | `devops vault sync [OPTIONS] <path>` | Synchronize secrets from Vault into OS Keyring for offline/local CLI operations. |
|  | `devops vault login [OPTIONS]` | Authenticate with Vault natively via AppRole or the in-cluster ServiceAccount. |
|  | `devops vault logout [OPTIONS]` | Revoke the token `devops vault login` stored, at the Vault that issued it, and delete it. |
|  | `devops vault leases [OPTIONS]` | Revoke a single Vault dynamic secret lease by id. |
|  | `devops vault audit [OPTIONS]` | Show which provider satisfied each credential lookup in this session. |
| [**valkey**](commands/valkey.md) | `devops valkey ping [OPTIONS]` | Test connection and measure round-trip latency to the Valkey server. |
|  | `devops valkey info [OPTIONS]` | Inspect server configuration, memory allocation, and operational metrics. |
|  | `devops valkey stats [OPTIONS]` | Display quick diagnostic summary of server health, memory, and keys. |
|  | `devops valkey keys [OPTIONS] <pattern>` | List keys matching a glob pattern. |
|  | `devops valkey get [OPTIONS] <key>` | Retrieve string value stored at key. |
|  | `devops valkey set [OPTIONS] <key> <value>` | Set string value of key with optional expiration TTL. |
|  | `devops valkey flush [OPTIONS]` | Flush and purge keys from current or all databases. |
|  | `devops valkey backup [OPTIONS]` | Trigger background RDB persistence snapshot (BGSAVE). |
|  | `devops valkey cli [OPTIONS] <command_args>` | Execute raw Valkey commands directly against the server. |
| [**sandbox**](commands/sandbox.md) | `devops sandbox deploy [OPTIONS] <command>` | Deploy an isolated background container sandbox with security containment. |
|  | `devops sandbox status [OPTIONS] <instance_id>` | Inspect status of deployed sandbox containers. |
|  | `devops sandbox stop [OPTIONS] <instance_id>` | Gracefully stop and tear down a sandbox container. |
|  | `devops sandbox exec [OPTIONS] <instance_id> <command>` | Execute a command inside an active sandbox container. |
|  | `devops sandbox probe [OPTIONS] <identifier>` | Probe endpoint readiness and service health across network protocols. |
|  | `devops sandbox metrics [OPTIONS] <identifier>` | Capture real-time cgroup v2 metrics and scrape Prometheus application metrics. |
|  | `devops sandbox traces [OPTIONS] <identifier>` | Visualize distributed trace waterfall and cross-service latency for sandbox workloads. |
|  | `devops sandbox logs [OPTIONS] <identifier>` | Stream stdout/stderr container logs with automated panic and crash detection. |
|  | `devops sandbox network-policy [OPTIONS]` | Generate declarative Kubernetes NetworkPolicy YAML for workload sandbox isolation. |
| [**dashboard**](commands/dashboard.md) | `devops dashboard [OPTIONS]` | Interactive terminal UI dashboard for workstation situational awareness. |
| [**tui**](commands/tui.md) | `devops tui [OPTIONS]` | Interactive terminal UI dashboard for workstation situational awareness. |
| [**status**](commands/status.md) | `devops status [OPTIONS]` | Inspect published operational status of upstream cloud platforms (GitHub, Cloudflare) |
| [**survey**](commands/survey.md) | `devops survey [OPTIONS]` | Outward-facing capability and upstream maturity survey. |
| [**research**](commands/research.md) | `devops research inventory [OPTIONS]` | List every pin of the project as a typed component: Python packages, tools, container images, GitHub Actions, Helm charts and Terraform providers. It reads files only. |
|  | `devops research advisories [OPTIONS]` | List the advisories that affect the pins of the project. It asks OSV about the Python and Node packages, and GitHub about the Actions and about the components that .devops/research-watch.toml maps to a repository. It flags a CVE of the CISA KEV list as exploited, and counts the components that no source matches. |
|  | `devops research sweep [OPTIONS]` | Run inventory and advisories, leave out the findings that an issue carries, and hand each actionable finding (severity critical or high) to roadmap intake as one candidate. Without --confirm, intake decides each candidate and writes nothing. It prints a digest and sets the gauge devops_cli_research_open_findings. |
| [**format**](commands/format.md) | `devops format [OPTIONS]` | Format codebase with ruff format (or verify in check-only mode with --check). |
| [**lint**](commands/lint.md) | `devops lint [OPTIONS]` | Run ruff linter across the project, automatically applying fixes by default. |
