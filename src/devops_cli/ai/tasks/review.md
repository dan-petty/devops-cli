## Code Review Protocol

Work through grounding, inspection, falsification, and formulation before reporting anything.

### 1. Ground the review in the target

- Judge against universal engineering principles (OWASP Top 10, CIS benchmarks, SOLID, DRY) and the conventions the target itself declares (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`). Never impose this CLI's layout, task structure or module names on another repository.
- Lockfiles (`uv.lock`, `package-lock.json`, `Cargo.lock`, `go.sum`) are authoritative. Never invent a CVE or a package warning against a pinned dependency.
- Separate production code from tests, mocks, fixtures, documentation and templates (`*.example.*`). A sample configuration or a tutorial explaining a vulnerability is not that vulnerability.

### 2. Inspect

- **Flow**: trace execution paths, boundary conditions, exception handling and resource lifecycles.
- **Symbols**: verify a module or symbol exists in the target before reporting a missing import or attribute. Check definitions, `__all__` and `__getattr__`. Never name a file or module you have not seen.
- **State after declaration**: never report a missing header, config key or request parameter from an initially empty structure (`headers = {}`). Trace mutations, environment fallbacks and conditional assignments through the whole function.
- **Path containment (CWE-22, CWE-59)**: filesystem writes, mount destinations, working directories and local stores must validate against traversal and refuse system paths. Directory walks (`os.walk`, `rglob`, `iterdir`) must skip symlinks (`is_symlink()`) and confirm the resolved path stays inside the repository.
- **Egress and SSRF**: outbound requests must resolve DNS and check every resolved address is non-private, before and after redirects. Hostname string matching alone does not survive DNS rebinding.
- **Timeouts**: a numeric timeout on an HTTP client must configure the `read` timeout while the connect timeout stays short. One value applied to both either hangs or fails fast for the wrong reason.
- **Complexity (CWE-400)**: find $O(N^2)$ AST unparsing, serialization or token counting inside loops; require single-pass budgeting. Bound string lengths and parsed JSON. Reading bounded local repository files or accumulating a CLI dictionary is not a denial of service — untrusted streams and unbounded buffers are.
- **Error detail (CWE-209)**: exception details and structured logs must bound caller-supplied strings (for example $\le 256$ chars) and mask credentials in URLs.
- **Rate limiting**: quota metrics (`remaining`, `limit`, `used`, `time_until_reset`) must stay $\ge 0$, delays must derive from live quota rather than a hardcoded window, and nested status resolution needs a re-entrant lock (`threading.RLock`).
- **Sandbox defaults**: sandbox and deployment tooling must default to an isolated network mode, not a host-accessible bridge. Flag an unconfined default offered without warning.
- **Secret hygiene**: command output, exception strings and fallback payloads from tooling wrappers must be masked before rendering, and a read cache must never store the result of an invocation carrying a token, password, cookie or authorization header.
- **Address hygiene**: published documentation must use RFC 5737 blocks (`192.0.2.0/24`) or placeholders, never a real RFC 1918 address. A NetworkPolicy must restrict sensitive ports to explicit namespaces and podSelectors rather than a broad RFC 1918 CIDR.
- **Ecosystem idioms**: valid modern syntax is not an error — Python 3.14 PEP 758 permits `except A, B:`. Redaction tokens (`<masked-*>`, `<secret-placeholder>`) are redactions. Prometheus exposition parsing that conforms to OpenMetrics is not an unvalidated metric name.

### 3. Falsify before reporting

- Search for what disproves the defect: surrounding guards, upstream sanitizers, lockfile pins, type guards, module exports, caller constraints.
- Cross-check against the hallucination catalog (`common_hallucinations.json`) and recorded feedback (`feedback_dataset.jsonl`). Drop a finding matching a catalogued false alarm.
- An abstract base class or mixin raising `NotImplementedError` for a method its subclasses implement is not a defect.
- Prefer a reproducible bug over a style preference. Drop the theoretical and the already-mitigated.

### 4. When the target is this repository

These resolve claims that recur against this codebase. Ignore them entirely when reviewing anything else.

- `Settings` resolves credentials from the OS keyring or the environment at runtime. It persists plaintext secrets only if unredacted credentials are written to disk.
- `sanitize_prompt_injection` strips delimiter tags to stop model hijacking. It omits HTML escaping deliberately: escaping `<`, `>` and `&` corrupts source code and comparisons on the way to a model. HTML escaping belongs in DOM rendering.
- Local cache tiers (Valkey, Redis, Memcached) are meant to run on loopback or a private cluster network. A private address configured for one is not SSRF.
- GitHub Actions reports `mergeable_state` as `"blocked"` while checks are in flight, so `--allow-blocked-state` in `.github/workflows/ci.yml` accommodates a transient state rather than bypassing a gate.
- JSON response repair lives in `response_repair.py`. There is no `ai/fixer.py`.

### 5. Formulate

- **Root cause**: name the failure mechanism, the exploit path and the blast radius, not the symptom.
- **Severity**:
  - **CRITICAL** — exploitable vulnerability, auth bypass, credential leak, SSRF, arbitrary write outside root, fatal crash.
  - **HIGH** — preconditioned vulnerability, data corruption, race, unvalidated path write, resource leak.
  - **MEDIUM** — bounded flaw, unhandled error state, incomplete mitigation.
  - **LOW** — hardening, observability, defense in depth, maintainability.
- **Fix**: a complete, self-contained replacement that resolves the defect without breaking an API contract.
- **Criteria**: 1–3 observable conditions that would demonstrate the defect (`verification_criteria`) and 1–3 that would show it absent or mitigated (`invalidation_criteria`). Keep each in its own field. These drive automated verification and test generation, so vague criteria make a finding unusable.
- **Roadmap**: where you see a worthwhile architectural improvement or integration beyond the defects, propose it as a candidate for `docs/ROADMAP.md`.
- **Approval**: with no actionable defect, return an empty findings array and `APPROVE`.
