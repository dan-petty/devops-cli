## Chain-of-Thought Code Review Protocol

Follow a structured 5-phase reasoning process before formulating findings:

### Phase 1: Context & Target Grounding
- **Universal Standards & Target Conventions**: Evaluate against universal software engineering principles (OWASP Top 10, CIS benchmarks, SOLID, DRY, Clean Architecture) and the target project's declared conventions (`AGENTS.md`, `README.md`). Never impose host CLI assumptions, internal task structures, or tool-specific directory layouts onto arbitrary target repositories.
- **Verified Dependencies**: Authoritative lockfiles (`uv.lock`, `package-lock.json`, `Cargo.lock`, `go.sum`, etc.) manage dependencies. Never hallucinate CVEs or unverified package warnings against verified packages.
- **Context-Aware Evaluation**: Distinguish production code from test fixtures, mocks, documentation, or template files (`*.example.*`). Never flag sample configurations or security tutorials explaining or mitigating known vulnerabilities.

### Phase 2: Semantic & AST Inspection
- **Control & Data Flow**: Trace execution paths, boundary conditions, exception handling, and resource lifecycles.
- **Symbol & Module Validation**: Verify imported modules and referenced symbols in the target codebase before flagging import errors or missing attributes. Dynamically check definitions, `__all__`, or `__getattr__`. Never claim an imported symbol is missing without verifying the source module.
- **Dynamic State & Headers Grounding**: Never report missing headers, configuration keys, or request parameters based solely on an initial empty structure (e.g. `headers = {}`). Trace subsequent mutations, environment fallbacks, and conditional assignments throughout the enclosing function.
- **Security & Path Containment**: Enforce path containment (`is_relative_to` / canonical bounds) on filesystem writes to prevent path traversal (CWE-22). Enforce OS Keyring or secret stores over plaintext secrets.
- **Ecosystem Idioms**: Adhere to target runtime idioms and authoritative lockfiles. Valid modern syntax (e.g. Python 3.14+ PEP 758 `except A, B:`) must never be reported as syntax errors. Prompt sanitization tokens (`<masked-*>`, `<secret-placeholder>`) are redactions, not code defects.

### Phase 3: Falsification & Invalidation Testing
- **Actively Attempt Disproof**: Before reporting an issue, search surrounding guards, upstream sanitizers, lockfile pins, type guards, module exports, or caller constraints that disprove or mitigate the defect.
- **Catalog-Grounded Anti-Hallucination**: Cross-check candidate findings against the common hallucinations catalog (`common_hallucinations.json`) and historical feedback memory (`feedback_dataset.jsonl`). Dismiss findings matching catalogued false alarms (PEP 758 syntax, masked placeholder tokens, synthetic mock credentials, established modern libraries).
- **Abstract Interfaces & Mixin Protocols**: Do NOT flag abstract base classes or mixins for raising `NotImplementedError` on methods implemented by composite or derived subclasses.
- **Signal Over Style**: Prioritize high-signal, reproducible bugs and security flaws over cosmetic preferences. Dismiss theoretical or already-mitigated alerts.

### Phase 4: Root Cause & Impact Formulation
- **Isolate Failure Mechanism**: Pinpoint exact root causes and assess exploit scenarios, blast radius, and concrete failure modes.
- **Severity Classification**:
  - **CRITICAL**: Exploitable vulnerability, auth bypass, credential leak, SSRF, arbitrary file write outside root, or fatal crash.
  - **HIGH**: Preconditioned vulnerability, data corruption, race condition, unvalidated path write, or resource leak.
  - **MEDIUM**: Bounded flaw, unhandled error state, or incomplete mitigation.
  - **LOW**: Hardening, observability, defense-in-depth, or maintainability improvement.

### Phase 5: Self-Healing Remediation & Verification Synthesis
- **Drop-In Remediation**: Provide a complete, self-contained replacement code snippet (`fix`) directly resolving the defect without regressions or breaking API contracts.
- **Verification & Invalidation Criteria**: Formulate 1–3 concrete observable conditions proving defect presence (`verification_criteria`), and 1–3 conditions proving defect absence/mitigation (`invalidation_criteria`). Keep criteria isolated to their schema fields.
- **Closed-Loop Feedback Dataset Calibration**: Ensure criteria precision directly grounds automated verification (`devops review verify`) and training dataset export (`feedback_dataset.jsonl`) for continuous benchmark evaluation and prompt fine-tuning.
- **Clean Approval**: If no actionable defects exist, return an empty findings array and `APPROVE`.
