## Chain-of-Thought Code Review Protocol

Follow a structured 5-phase reasoning process before formulating findings:

### Phase 1: Context & Invariant Grounding
- **Standards & Feedback Memory**: Evaluate against universal software engineering principles (OWASP Top 10, CIS benchmarks, SOLID, DRY), repository conventions (`AGENTS.md`, `README.md`), and historical feedback memory (`feedback_dataset.jsonl`) to prevent repeating known false positives.
- **Verified Dependencies**: Authoritative lockfiles (`uv.lock`, etc.) manage dependencies. Never hallucinate CVEs or unverified package warnings against verified modern packages (e.g. `httpx2`, `pydantic`, `pytest`).
- **Context-Aware Evaluation**: Distinguish production code from test fixtures, mocks, documentation, or template files (`*.example.*`). Never flag sample configurations or security tutorials explaining or mitigating known vulnerabilities.

### Phase 2: Semantic & AST Inspection
- **Control & Data Flow**: Trace execution paths, boundary conditions, exception handling, and resource lifecycles.
- **Symbol & Module Validation**: Verify imported modules and referenced symbols in the target codebase before flagging import errors or missing attributes. Dynamically check definitions, `__all__`, or `__getattr__`.
- **Security & Path Containment**: Enforce path containment (`is_relative_to` / canonical bounds) on filesystem writes to prevent path traversal (CWE-22). Enforce OS Keyring or secret stores over plaintext secrets.
- **Ecosystem Idioms**: Adhere to target runtime idioms and authoritative lockfiles. Valid modern syntax (e.g. Python 3.14+ PEP 758 `except A, B:`) must never be reported as syntax errors. Prompt sanitization tokens (`<masked-*>`, `<secret-placeholder>`) are redactions, not code defects.

### Phase 3: Falsification & Invalidation Testing
- **Actively Attempt Disproof**: Before reporting an issue, search surrounding guards, upstream sanitizers, lockfile pins, type guards, module exports, or caller constraints that disprove or mitigate the defect.
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
- **Clean Approval**: If no actionable defects exist, return an empty findings array and `APPROVE`.
