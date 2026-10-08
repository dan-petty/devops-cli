# Review Conventions: devops-cli

`devops ai review` reads this file in full when it reviews this repository, and gives it to the
persona reviewers and to the verifier. It holds the rules that are true here and not in general.
The shared review prompts stay project-agnostic; see `docs/SELF_IMPROVEMENT.md`.

## Python and types

- The package requires Python 3.14 (`requires-python = ">=3.14"`). PEP 758's unparenthesized
  multi-exception clause (`except A, B:`) is valid here, and Ruff formats code that way.
- The package passes `mypy --strict`. A None-dereference claim against an attribute that is not
  declared Optional (`X | None`) at its definition is false, unless the value crosses an untyped
  boundary (`Any`, `getattr`, parsed JSON, `**kwargs`).

## What this tool is

A DevOps CLI reaches internal infrastructure and prints what it is working on. Both are its
purpose, not defects.

- **Internal connectors**: SSRF claims against infrastructure connectors that reach private
  networks are not defects. Valkey, the Vault broker, the Kubernetes API, Loki, Prometheus,
  Grafana and a configured Ollama or gateway reach them by design. HTTP clients built by the
  `devops_cli.http.client` factory are checked at the connect at their egress level: the Vault
  broker, the Kubernetes clients and the sandbox probe at private (`EgressLevel.PRIVATE`), the
  LLM client base at the configured level, which `ai.allow_private_network` widens to private.
  Every level refuses cloud metadata. The other connectors are not checked at the connect yet
  and validate their URL before the request with `allow_private_network`. SSRF still applies to
  public-level callers and user-supplied external URLs (web fetchers, document retrievers, user
  webhooks): one fetched below the public level, or dialled outside the factory, is a finding.
- **Internal HTTP**: the model backends (`http://ollama:*`, `http://vllm:*`, `http://qdrant:*`)
  and the loopback defaults (`http://localhost:*`, `127.0.0.1`) are plain HTTP by design.
- **Console output**: information-exposure (CWE-200) claims about terminal output, debug logging
  of paths under inspection, or progress indicators are not defects.
- **Local input**: CWE-400 claims about reading repository files (`pyproject.toml`, schemas,
  markdown, lockfiles, local config) or building output collections during a CLI run are not
  defects.

## Threat model

- **Trusted here**: `config.yaml`, `DEVOPS_*` and provider environment variables, keyring
  entries, command-line arguments, and the user's workspace and repositories where devops-cli
  acts on them for the user (`ci`, `workspace`, `git`).
- **Untrusted here**: a tree devops-cli reviews, scans, analyzes or ingests, even when it is the
  user's own, since an agent or contributor writes the branch (#946); pages and documents fetched
  by web fetch or docs ingestion, model replies and tool-call arguments, GitHub PR, issue and
  comment text, Kubernetes API data (logs, events, Popeye and scanner output), MCP client calls,
  and HTTP requests to the local server (`src/devops_cli/server`).

## Documentation and configuration

- A concrete RFC 1918 address (`10.x`, `172.16-31.x`, `192.168.x`) or a real `.local` or `.lan`
  host name in published documentation, `k8s/` manifests or tests is a finding: use abstract
  roles (`<storage-node>`, `<gpu-node>`) instead.
- A NetworkPolicy that opens broad RFC 1918 ranges to sensitive ports without namespace scoping is
  a finding.

## House rules

- **Directory walks** (`os.walk`, `rglob`, `iterdir`) must skip symlinks (`is_symlink()`) and
  confirm the resolved path stays inside the repository.
- **HTTP timeouts**: a numeric timeout on an HTTP client configures the `read` timeout while the
  connect timeout stays short. One value applied to both either hangs or fails fast for the wrong
  reason.
- **Quadratic work**: AST unparsing, serialization or token counting inside loops needs
  single-pass budgeting.
- **Error detail (CWE-209)**: caller-supplied strings in exception details and structured logs are
  bounded, for example to 256 characters.
- **Rate limiting**: quota metrics (`remaining`, `limit`, `used`, `time_until_reset`) stay at or
  above zero, delays derive from live quota rather than a hardcoded window, and nested status
  resolution needs a re-entrant lock (`threading.RLock`).
- **Sandbox defaults**: sandbox and deployment tooling defaults to an isolated network mode, not a
  host-accessible bridge.
- **Tool wrappers**: command output, exception strings and fallback payloads from tooling wrappers
  are masked before rendering, and a read cache never stores the result of an invocation carrying
  a token, password, cookie or authorization header.
- **Pre-1.0 hygiene**: until 1.0 the codebase carries no legacy shims, vestigial fallbacks or
  compatibility workarounds, and a changed flag or schema is intended, not a breaking defect.

## Settled claims

These resolve claims that recur against this codebase.

- `Settings` resolves credentials from the OS keyring or the environment at runtime. It persists
  plaintext secrets only if unredacted credentials are written to disk.
- `sanitize_prompt_injection` strips delimiter tags to stop model hijacking. It omits HTML escaping
  deliberately: escaping `<`, `>` and `&` corrupts source code on the way to a model. HTML escaping
  belongs in DOM rendering.
- Local cache tiers (Valkey, Redis, Memcached) run on loopback or a private cluster network. A
  private address configured for one is not SSRF.
- GitHub Actions reports `mergeable_state` as `"blocked"` while checks are in flight, so
  `--allow-blocked-state` in `.github/workflows/ci.yml` accommodates a transient state rather than
  bypassing a gate.
- Prometheus exposition parsing that conforms to OpenMetrics is not an unvalidated metric name, and
  instant queries (`/api/v1/query`) are well formed.
- JSON response repair lives in `response_repair.py`. There is no `ai/fixer.py`.
- `docs/ROADMAP.md` and task files under `docs/agent/tasks/` record plans and history.
- Structural tuple comparisons in test assertions (`assert (a, b) == (x, y)`) cap McCabe
  complexity at 10; they are not assertion bugs.
- `tests/golden/*` and `tests/fixtures/*` hold synthetic vulnerability exemplars on purpose.
- NodePort services in the `k8s/` manifests and Helm values are how workstations reach a
  minikube or homelab cluster; that exposure is intended, not a finding.
- `httpx2`, `pydantic` and `pytest`, declared in `pyproject.toml` and `uv.lock`, are approved.
- Pricing ledgers and token estimators split URLs (`urlsplit`) without a request: not SSRF.
- Audit and mitigation ledgers start empty (`mitigations = []`) and fill as checks run.
- GraphQL requests send `json.dumps()` of the query and variables; that is not double encoding.
- `ast.parse` of reviewed files ignores `SyntaxWarning` on purpose; invalid syntax still raises.
- `common_hallucinations.json`, the review prompts and exemplar datasets quote bad patterns to
  detect them.
- Hardware daemonsets (NVIDIA GPU Feature Discovery, DCGM Exporter, device plugins) need
  privileged host access (`privileged: true`, `runAsUser: 0`, `SYS_ADMIN`, `/dev/nvidia*`).
- LLM profile NetworkPolicies allow egress to `0.0.0.0/0` to pull model weights and block
  `169.254.169.254/32`. Egress rules scope by pod and namespace selectors without `ports:`,
  because kube-router drops traffic for rules that combine them.
- LightLLM and other removed backends are decommissioned, not missing.
- Jaeger v2 ships as `jaegertracing/jaeger`; `jaegertracing/all-in-one` is v1.
- Metric labels holding an exception class name (`type(exc).__name__`) expose nothing.
- Tenacity retries pass `HTTPStatusError` through `is_retryable_status_code`, so 4xx client
  errors are not retried.
- `aclose_shared_clients()` clears `_ASYNC_CLIENTS` under its lock before awaiting the closes.
