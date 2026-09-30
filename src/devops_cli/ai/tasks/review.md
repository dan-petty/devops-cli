## Code Review Protocol

Work through grounding, inspection, falsification, and formulation before reporting anything.

### 1. Ground the review in the target

- Judge against universal engineering principles (OWASP Top 10, CIS benchmarks, SOLID, DRY) and the conventions the target itself declares (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`, `.devops/review.md`). Those conventions decide what is intended in that project; never impose one project's rules on another.
- Lockfiles (`uv.lock`, `package-lock.json`, `Cargo.lock`, `go.sum`) record exact versions. A vulnerability claim against a pinned dependency must cite a real advisory identifier; never invent one.
- Separate production code from tests, mocks, fixtures, golden test datasets (`tests/golden/*`), documentation and templates (`*.example.*`). Test fixtures containing deliberate vulnerability exemplars, dummy keys (`sk-gateway`, `example.com`), or documentation placeholders (`ghp_your_personal_access_token`) are not production vulnerabilities.
- Internal cluster overlay networking (`http://*.svc.cluster.local`) and backend service connections (`http://ollama:*`, `http://vllm:*`, `http://qdrant:*`) within private cluster boundaries are intentional infrastructure mechanisms, not plaintext exposure defects.
- Offline cost calculators, pricing ledgers, and token estimators that split or parse URLs lexically (`urllib.parse.urlsplit`) in memory without socket I/O are not SSRF or network egress vulnerabilities.
- Initializing audit, telemetry, or mitigation ledgers with an empty list (`mitigations = []`) is standard dynamic accumulator initialization, not an absent mitigation defect.
- Structural tuple equality assertions in test suites (`assert (a, b) == (x, y)`) are mandatory architectural invariants to cap cyclomatic complexity $M \le 10$, not faulty assertion logic.
- Default configuration fallback URLs pointing to localhost (`127.0.0.1`, `http://localhost:*`) are mandated for configuration hygiene, not SSRF vulnerabilities.
- Verified dependencies (`httpx2`, `pydantic`, `pytest`) declared in `pyproject.toml` and lockfiles are approved packages; never claim they are malicious or untrusted.
- Pre-1.0 software guarantees zero backwards compatibility; flag alterations or interface evolutions are intentional evolutions, not breaking defects.
- GraphQL endpoints over HTTP POST require standard JSON payloads with query strings and variable mappings (`json.dumps()`); this is not double-encoding or payload corruption.
- Sample or fallback webhooks pointing to RFC 2606 domains (`example.com`, `example.org`) or `localhost` are standard documentation/template placeholders, not reachability or security defects.
- Prometheus instant query endpoints (`/api/v1/query`) and OpenTelemetry metrics follow standard telemetry conventions; querying them is not a syntax or query flaw.
- Hardware discovery daemonsets and hardware exporters (such as NVIDIA GPU Feature Discovery, NVIDIA DCGM Exporter, or device plugins) legitimately require privileged host access (`runAsUser: 0`, `privileged: true`, `SYS_ADMIN`) and host character devices (`/dev/nvidia*`, NVML) to discover hardware topology and collect metrics.
- Outbound internet egress (`0.0.0.0/0`) in Kubernetes NetworkPolicy for LLM profiles (Ollama, vLLM) is required for pulling model weights from public model registries (HuggingFace, Ollama Registry); metadata endpoints (`169.254.169.254/32`) are blocked.
- Deliberately decommissioned components or backends (such as LightLLM) under pre-1.0 software lifecycle are not missing features or defects.
- GitHub login handles are normalized alphanumeric identifiers; author comparison logic does not require case folding or whitespace stripping.
- Task tracking documents (`docs/agent/tasks/task-*.md`) describe planning milestones and tracking history, not production runtime code defects.
- Jaeger v2 is an OpenTelemetry-native binary distributed as `jaegertracing/jaeger`, whereas `all-in-one` is the deprecated v1 distribution.
- Telemetry metric labels recording exception class names (`type(exc).__name__`) represent standard failure classification, not information exposure (CWE-200).
- Tenacity retry transports raising `HTTPStatusError` in `default_validate` are filtered by downstream retry predicates (`is_retryable_status_code`); client errors (400, 401, 403, 404, 422) are not retried.

### 2. Inspect

- **Flow**: trace execution paths, boundary conditions, exception handling and resource lifecycles.
- **Symbols**: verify a module or symbol exists in the target before reporting a missing import or attribute. Check definitions, `__all__` and `__getattr__`. Never name a file or module you have not seen.
- **State after declaration**: never report a missing header, config key or request parameter from an initially empty structure (`headers = {}`). Trace mutations, environment fallbacks and conditional assignments through the whole function.
- **Path containment (CWE-22, CWE-59)**: filesystem reads and writes of paths a user or caller influences must validate against traversal and refuse system paths.
- **Egress and SSRF**: requests to URLs a user supplies must resolve DNS and check every resolved address is non-private, before and after redirects. Hostname string matching alone does not survive DNS rebinding.
- **Complexity (CWE-400)**: find the same expensive work (parsing, serialization, counting) repeated inside loops over the same data. Bound string lengths and parsed input from outside. Reading the project's own files is not a denial of service; untrusted streams and unbounded buffers are.
- **Error detail (CWE-209)**: exception details and structured logs must bound caller-supplied strings and mask credentials in URLs.
- **Secret hygiene**: secrets must not reach logs, exception strings, rendered output or caches.
- **Ecosystem idioms**: syntax valid for the language version the project declares is not an error; read that version before calling a construct invalid. Redaction tokens (`<masked-*>`, `<secret-placeholder>`) are inserted by the review tool, not written in the code.

### 3. Falsify before reporting

- Search for what disproves the defect: surrounding guards, upstream sanitizers, lockfile pins, type guards, module exports, caller constraints.
- An abstract base class or mixin raising `NotImplementedError` for a method its subclasses implement is not a defect.
- Prefer a reproducible bug over a style preference, and drop the purely theoretical. When something limits a real defect, report it anyway: name the mitigation and where it is, and lower the severity.

### 4. Formulate

- **Root cause**: name the failure mechanism, the exploit path and the blast radius, not the symptom.
- **Severity**:
  - **CRITICAL** — exploitable vulnerability, auth bypass, credential leak, SSRF, arbitrary write outside root, fatal crash.
  - **HIGH** — preconditioned vulnerability, data corruption, race, unvalidated path write, resource leak.
  - **MEDIUM** — bounded flaw, unhandled error state, incomplete mitigation.
  - **LOW** — hardening, observability, defense in depth, maintainability.
- **Fix**: a complete, self-contained replacement that resolves the defect without breaking an API contract.
- **Criteria**: 1–3 observable conditions that would demonstrate the defect (`verification_criteria`) and 1–3 that would show it absent or mitigated (`invalidation_criteria`). Criteria drive automated verification in a bounded sandbox: each must either be an executable command from the closed read-only allowlist (`git grep`, `git ls-files`, `python -c`, `ruff check`, `pytest`) marked with `executable: true` (or a raw allowlisted command string), or explicitly marked with `executable: false` if unexecutable prose. Bare unexecutable prose must not be marked executable. Never write tautological criteria that merely confirm file content or reflection symbols (e.g. `git grep`, `grep`, `hasattr`, `co_varnames`). Criteria must execute logic or assertions demonstrating the defect or failure behavior, not trivial existence. When formulating Python commands (`python -c "..."`) in criteria, always use raw strings (`r'...'`) or double backslashes (`\\w`, `\\s`, `\\d`, `\\b`) to prevent invalid escape sequence syntax warnings.
- **Verdict Polarity**: When asserting a discrepancy between code behavior and expected standards, provide both `observed_value` and `expected_value`. Never provide one without the other, and never emit identical values (`observed_value == expected_value`); findings asserting identical values are contradictory hallucinations and will be invalidated.
- **Suggestions and narrative summaries are not findings**: narrative summaries of documentation, compliments ('The documentation correctly explains...'), or improvements that fix no defect belong in `summary`, never in `findings`.
- **Approval**: with no actionable defect, return an empty findings array and `APPROVE`.
