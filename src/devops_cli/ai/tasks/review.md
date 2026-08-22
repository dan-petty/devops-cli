## Atomic Review Protocol
Perform an objective, evidence-grounded code review:

1. **Defect Identification & Self-Improvement**:
   - Evaluate code against universal principles (security, reliability, maintainability, strict typing).
   - Evaluate the target project against its own documented conventions (`AGENTS.md`/`README.md`).
   - Enforce purpose-driven, functional naming: file/folder names, classes, functions, and variables must clearly describe the concrete function and purpose of the code they contain.
   - Do NOT flag documentation, test assertions/fixtures, template files (`*.example.*`), or historical logs.
   - Respect modern language features and idiomatic syntax (e.g. Python 3.14+ `except (Err1, Err2):`).
   - If no actionable defects are identified, return an empty `findings` array and `APPROVE`.

2. **Verification & Invalidation Criteria**:
   - For every finding, supply:
     - `verification_criteria`: 1-3 concrete conditions in code proving the defect is present.
     - `invalidation_criteria`: 1-3 conditions, mitigations, or surrounding guardrails that would prove it a false positive.

3. **Actionable Remediation**:
   - Provide concrete replacement code (`fix`) and standards references (`references`). Ensure fixes are self-contained drop-in solutions.

## Severity Scale
- **CRITICAL**: Exploitable vulnerability, auth bypass, credential leak, or fatal runtime crash.
- **HIGH**: Preconditioned vulnerability, data corruption, race condition, or resource leak.
- **MEDIUM**: Bounded blast radius flaw, unhandled error state, or incomplete mitigation.
- **LOW**: Hardening, observability, or defense-in-depth improvement without direct exploit path.

## Finding Schema (JSON)
Each finding must contain:
- `severity`: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
- `location`: "path/to/file.ext:start-end"
- `title`: Concise summary
- `description`: Defect explanation and concrete impact scenario
- `fix`: Replacement code or exact configuration snippet
- `verification_criteria`: String array of proving conditions
- `invalidation_criteria`: String array of disproving conditions
- `references`: List of CVE / CWE / RFC / NIST / SOC references

## Merge Recommendation
- **BLOCK**: Unmitigated CRITICAL findings.
- **REQUEST CHANGES**: Unresolved HIGH, MEDIUM, or LOW findings.
- **APPROVE**: Sound code with zero findings.
