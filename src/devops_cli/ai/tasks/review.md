## Atomic Review Protocol
Perform an objective, evidence-grounded code review:

1. **Defect Identification & Evidence Grounding**:
   - Evaluate code against universal principles (security, reliability, maintainability, strict static typing, SSRF defense, zero-trust secrets).
   - Evaluate the target project against its own documented conventions (`AGENTS.md`, `README.md`, or architecture guides).
   - Utilize injected `<rag_context>` and analysis metadata to cross-reference module boundaries, interfaces, and shared types.
   - Enforce purpose-driven, functional naming: file/folder names, classes, functions, and variables must clearly describe the concrete function and purpose of the code they contain.
   - Do NOT flag documentation, test assertions/fixtures, test mocks, template files (`*.example.*`), or historical review logs.
   - Respect modern language features and idiomatic syntax (e.g. Python 3.14+ `except (Err1, Err2):`, Pydantic V2 models, strict type annotations).
   - If no actionable defects are identified, return an empty `findings` array and `APPROVE`.

2. **Self-Improvement & Closed Feedback Loop**:
   - Prioritize high-signal, reproducible, and verifiable defects over stylistic or theoretical micro-optimizations.
   - Learn from codebase architectural standards and prior verified findings to eliminate repetitive false positives.
   - Provide clear root-cause explanations and concrete impact scenarios for each identified flaw.
   - Supply self-contained drop-in replacement code (`fix`) that satisfies the repository's formatting, strict typing, and security standards.
   - Include concrete verification instructions so developers and automated test suites can deterministically prove resolution.

3. **Verification & Invalidation Criteria**:
   - For every finding, supply:
     - `verification_criteria`: 1-3 concrete conditions in visible code proving the defect is present.
     - `invalidation_criteria`: 1-3 conditions, surrounding guardrails, or architectural mitigations proving the defect is absent or a false positive.

## Severity Scale
- **CRITICAL**: Exploitable vulnerability, auth bypass, credential leak, SSRF, or fatal runtime crash.
- **HIGH**: Preconditioned vulnerability, data corruption, race condition, missing resource limits, or resource leak.
- **MEDIUM**: Bounded blast radius flaw, unhandled error state, or incomplete mitigation.
- **LOW**: Hardening, observability, defense-in-depth, or maintainability improvement without direct exploit path.

## Finding Schema (JSON)
Each finding must contain:
- `severity`: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
- `location`: "path/to/file.ext:start-end"
- `title`: Concise summary
- `description`: Defect explanation, root cause, and concrete impact scenario
- `fix`: Replacement code or exact configuration snippet
- `verification_criteria`: String array of proving conditions
- `invalidation_criteria`: String array of disproving conditions
- `references`: List of CVE / CWE / RFC / NIST / OWASP references

## Merge Recommendation
- **BLOCK**: Unmitigated CRITICAL findings.
- **REQUEST CHANGES**: Unresolved HIGH, MEDIUM, or LOW findings.
- **APPROVE**: Sound code with zero findings.
