## Code Review Protocol

Work through grounding, inspection, falsification, and formulation before reporting anything.

### 1. Ground the review in the target

- Judge against universal engineering principles (OWASP Top 10, CIS benchmarks, SOLID, DRY) and the conventions the target itself declares (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`, `.devops/review.md`). Those conventions decide what is intended in that project; never impose one project's rules on another.
- Lockfiles (`uv.lock`, `package-lock.json`, `Cargo.lock`, `go.sum`) record exact versions. A vulnerability claim against a pinned dependency must cite a real advisory identifier; never invent one.
- Separate production code from tests, mocks, fixtures, golden test datasets (`tests/golden/*`), documentation and templates (`*.example.*`). Test fixtures containing deliberate vulnerability exemplars or dummy keys (`sk-gateway`, `example.com`) are not production vulnerabilities. Internal cluster overlay networking (`http://*.svc.cluster.local`) and local workstation NodePort services are intentional infrastructure mechanisms, not defects.
- Structural tuple equality assertions in test suites (`assert (a, b) == (x, y)`) are mandatory architectural invariants to cap cyclomatic complexity $M \le 10$, not faulty assertion logic.
- Default configuration fallback URLs pointing to localhost (`127.0.0.1`, `http://localhost:*`) are mandated for configuration hygiene, not SSRF vulnerabilities.
- Verified dependencies (`httpx2`, `pydantic`, `pytest`) declared in `pyproject.toml` and lockfiles are approved packages; never claim they are malicious or untrusted.
- Pre-1.0 software guarantees zero backwards compatibility; flag alterations or interface evolutions are intentional evolutions, not breaking defects.

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
- **Criteria**: 1–3 observable conditions that would demonstrate the defect (`verification_criteria`) and 1–3 that would show it absent or mitigated (`invalidation_criteria`). Criteria drive automated verification in a bounded sandbox: each must either be an executable command from the closed read-only allowlist (`git grep`, `git ls-files`, `python -c`, `ruff check`, `pytest`) marked with `executable: true` (or a raw allowlisted command string), or explicitly marked with `executable: false` if unexecutable prose. Bare unexecutable prose must not be marked executable.
- **Verdict Polarity**: When asserting a discrepancy between code behavior and expected standards, provide both `observed_value` and `expected_value`. Never provide one without the other, and never emit identical values (`observed_value == expected_value`); findings asserting identical values are contradictory hallucinations and will be invalidated.
- **Suggestions and narrative summaries are not findings**: narrative summaries of documentation, compliments ('The documentation correctly explains...'), or improvements that fix no defect belong in `summary`, never in `findings`.
- **Approval**: with no actionable defect, return an empty findings array and `APPROVE`.
