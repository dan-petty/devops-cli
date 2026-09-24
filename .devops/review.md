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

- **Internal connectors**: SSRF claims against infrastructure connectors that set
  `allow_private_network=True` (Valkey, the Vault broker, the Kubernetes API, Prometheus, Grafana,
  a local Ollama) are not defects. SSRF applies to user-supplied external URLs: web fetchers,
  document retrievers, user webhooks.
- **Console output**: information-exposure (CWE-200) claims about terminal output, debug logging
  of paths under inspection, or progress indicators are not defects.
- **Local input**: CWE-400 claims about reading repository files (`pyproject.toml`, schemas,
  markdown, lockfiles, local config) or building output collections during a CLI run are not
  defects.

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
  compatibility workarounds.

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
- Prometheus exposition parsing that conforms to OpenMetrics is not an unvalidated metric name.
- JSON response repair lives in `response_repair.py`. There is no `ai/fixer.py`.
