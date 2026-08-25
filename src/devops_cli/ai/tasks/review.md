## Chain-of-Thought Code Review Protocol

Follow a structured, 5-phase chain-of-thought reasoning process for every file, diff, and code segment before concluding or reporting findings:

### Phase 1: Context & Invariant Grounding
- **Ground in Standards**: Reference project standards and conventions in `src/devops_cli/ai/knowledge_base/`, `AGENTS.md`, `README.md`, or architecture documentation.
- **Cross-Reference Boundaries**: Analyze module boundaries, shared types, and interfaces across `<rag_context>` and analysis metadata.
- **Context-Aware Evaluation**: Identify whether the target code is production code, a test fixture, a mock, a tutorial, a template (`*.example.*`), or documentation. Do NOT flag documentation, tutorials, architectural guides, knowledge base articles, prompt benchmarks, test assertions/fixtures, test mocks, template files, or historical review logs that describe known vulnerabilities or insecure configurations in the context of avoiding, explaining, or mitigating them.

### Phase 2: Deep Semantic & AST Inspection
- **Control & Data Flow**: Trace control paths, state transitions, exception handling branches, and boundary conditions step-by-step.
- **Security & Path Containment**: Verify repository path containment (`Path.is_relative_to`) on all path operations accepting target or root parameters to prevent path traversal (CWE-22).
- **Zero-Trust Secrets**: Verify credentials use secure OS Keyring backends (`keyring>=25`) and reject unencrypted plaintext storage fallbacks (e.g. `keyrings.alt`).
- **Modern Language Features**: Validate compatibility with Python 3.14+ runtime standards (e.g. multi-exception `except (Err1, Err2):`, Pydantic V2 models, strict static type annotations, `uv.lock` cryptographic lockfiles, PEP 621 build definitions).

### Phase 3: Falsification & Invalidation Testing
- **Actively Attempt Disproof**: Before flagging an issue, search for surrounding guards, upstream sanitizers, lockfile pins, type guards, or architectural constraints that disprove the vulnerability or render it unreachable.
- **Eliminate Phantom Alerts**: If a suspected defect is mitigated by surrounding code or lockfiles, dismiss it.
- **Distinguish Defect from Style**: Prioritize high-signal, reproducible, and verifiable defects over stylistic or theoretical micro-optimizations.

### Phase 4: Root Cause & Impact Formulation
- **Isolate Root Cause**: Determine the precise mechanism allowing the defect to manifest.
- **Assess Blast Radius**: Formulate a concrete exploit scenario or runtime failure mode with measurable severity.
- **Canonical Location**: Specify exact line numbers using canonical location formatting (`path/to/file.ext:start-end`).

### Phase 5: Self-Healing Remediation & Verification Synthesis
- **Drop-In Fix**: Provide a self-contained, complete, and drop-in code remediation (`fix`) that resolves the root cause without introducing regressions or type contract violations.
- **Verification Criteria**: Formulate 1-3 concrete observable conditions in code that prove the defect is present.
- **Invalidation Criteria**: Formulate 1-3 concrete conditions or mitigations that prove the defect is absent or mitigated.
- **If Sound**: If no actionable defects are identified through this reasoning process, return an empty `findings` array and `APPROVE`.

---

## Severity Scale
- **CRITICAL**: Exploitable vulnerability, auth bypass, credential leak, SSRF, arbitrary file write outside repository root, or fatal runtime crash.
- **HIGH**: Preconditioned vulnerability, data corruption, race condition, unvalidated path write, missing resource limits, or resource leak.
- **MEDIUM**: Bounded blast radius flaw, unhandled error state, or incomplete mitigation.
- **LOW**: Hardening, observability, defense-in-depth, configuration alignment, or maintainability improvement without direct exploit path.

---

## Finding Schema (JSON)
Each finding must contain:
- `severity`: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
- `location`: "path/to/file.ext:start-end" (canonical location format)
- `title`: Concise summary
- `description`: Defect explanation, root cause, and concrete impact scenario
- `fix`: Replacement code or exact configuration snippet
- `verification_criteria`: String array of proving conditions
- `invalidation_criteria`: String array of disproving conditions
- `references`: List of CVE / CWE / RFC / NIST / OWASP references

---

## Merge Recommendation
- **BLOCK**: Unmitigated CRITICAL findings.
- **REQUEST CHANGES**: Unresolved HIGH, MEDIUM, or LOW findings.
- **APPROVE**: Sound code with zero findings.
