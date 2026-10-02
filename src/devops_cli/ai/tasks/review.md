## Code Review Protocol

Work through grounding, inspection, falsification, and formulation before reporting anything.

### 1. Ground the review in the target

- Judge against universal engineering principles (OWASP Top 10, CIS benchmarks, SOLID, DRY) and the conventions the target itself declares (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`, `.devops/review.md`). Those conventions decide what is intended in that project; never impose one project's rules on another.
- Lockfiles (`uv.lock`, `package-lock.json`, `Cargo.lock`, `go.sum`) record exact versions. Dependency advisories come from the scanners; do not report one yourself.
- Separate production code from tests, mocks, fixtures, golden datasets, documentation and templates (`*.example.*`). Dummy keys, documentation placeholders (`ghp_your_personal_access_token`) and `example.com` addresses are not secrets or production vulnerabilities.
- Plain `http://` between services inside a cluster or private network (`http://*.svc.cluster.local`) is not plaintext exposure.

### 2. Inspect

- **Flow**: trace execution paths, boundary conditions, exception handling and resource lifecycles.
- **Symbols**: verify a module or symbol exists in the target before reporting a missing import or attribute. Check definitions, `__all__` and `__getattr__`. Never name a file or module you have not seen.
- **State after declaration**: never report a missing header, config key or request parameter from an initially empty structure (`headers = {}`). Trace mutations, environment fallbacks and conditional assignments through the whole function.
- **Path containment (CWE-22, CWE-59)**: a file path built from untrusted input must be checked to stay inside its root and refuse system paths.
- **Egress and SSRF**: an untrusted URL must have every resolved address checked as non-private, before and after redirects. Hostname string matching alone does not survive DNS rebinding.
- **Complexity (CWE-400)**: find the same expensive work (parsing, serialization, counting) repeated inside loops over the same data, and untrusted input or streams with no bound. Reading the project's own files is not a denial of service.
- **Error detail (CWE-209)**: an untrusted string must be bounded before it reaches an exception detail or a structured log, and a URL's credentials masked.
- **Secret hygiene**: secrets must not reach logs, exception strings, rendered output or caches.
- **Ecosystem idioms**: syntax valid for the language version the project declares is not an error; read that version before calling a construct invalid.
- **Masking markers**: the review tool replaces values it takes for secrets with markers of the form `<masked-kind>` (`<masked-token>`) before you read the file. Never report such a marker as a hardcoded secret, a syntax error or a broken value. A bare `<masked>` or any other mask is the file's own text.

### 3. Falsify before reporting

- Search for what disproves the defect: surrounding guards, upstream sanitizers, lockfile pins, type guards, module exports, caller constraints.
- Report only what you can see. If showing the defect needs code you were not given, return no finding.
- A requirement is not a defect. Report the line that breaks it, or nothing.
- An abstract base class or mixin raising `NotImplementedError` for a method its subclasses implement is not a defect.
- Prefer a reproducible bug over a style preference, and drop the purely theoretical. When something limits a real defect, report it anyway: name the mitigation and where it is, and lower the severity.

### 4. Formulate

- **Root cause**: name the failure mechanism, the path to it and the blast radius, not the symptom.
- **Trusted and untrusted input** are what the project's conventions say they are. Where the conventions give no threat model, untrusted input is network and fetched content, model output, pull request and issue text, a repository the program reviews or builds, cluster and cloud API data, requests to a server the code runs, and tool-call arguments; the operator's config, environment and arguments, and values the code builds, are trusted.
- **Severity** follows who can trigger the defect and what it costs:
  - **CRITICAL** — an untrusted input reaches code execution, credential disclosure, or a write outside its root, and you can quote every step.
  - **HIGH** — an untrusted input reaches harm under a precondition you state, or normal use corrupts or loses data.
  - **MEDIUM** — wrong behaviour on a path normal use reaches: a crash, an unhandled error, a leak in a long-running process.
  - **LOW** — hardening, defense in depth, a missing guard on trusted input that the project's conventions require. Without that requirement, a missing guard on trusted input is no finding.
- **Fix**: replacement code for the cited lines that would make your verification check fail. If the fix is to verify, review, consider or investigate, or if it matches the current code, there is no finding.
- **Observed and expected**: `observed_value` is the defective code or text copied exactly from the cited lines; `expected_value` is what it should be. They must differ.
- **Criteria**: `verification_criteria` holds 1–3 checks that pass only while the defect exists; `invalidation_criteria` holds 1–3 that pass only when it is absent. An executable check (`"executable": true`) is a `python -c` or `pytest` command that imports the cited code, runs it on the input your description names, and `assert`s the outcome. A command that only finds, imports or prints code proves nothing; write that check as a sentence with `"executable": false`. Use raw strings for regular expressions in `python -c`.
- **Not findings**: summaries of the code, compliments, and improvements that fix no defect belong in `summary`.
- **No defect**: return an empty `findings` array.
