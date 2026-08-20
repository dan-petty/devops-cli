## Atomic Review Protocol & Micro-Steps
Perform a structured, evidence-grounded review broken into atomic steps:

1. **Step 1: Pattern & Defect Identification**:
   - Analyze visible code objectively. Cite exact file paths and line numbers.
   - Evaluate code against universal software engineering principles (security, reliability, maintainability, type safety, testability).
   - Evaluate the target project based on its own documented conventions (`AGENTS.md` / `README.md`) rather than imposing host project directory layout or arbitrary naming rules.
   - Do NOT flag documentation, template files (`*.example.*`), or historical logs.
   - Respect modern language runtime syntax (e.g. Python exception tuples `except (Err1, Err2):`).

2. **Step 2: Define Verification & Invalidation Criteria**:
   - For every finding, provide explicit criteria:
     - `verification_criteria`: 1-3 concrete, observable conditions that prove the defect is present in the code.
     - `invalidation_criteria`: 1-3 concrete conditions, mitigations, or context that would disprove the defect or render it a false positive.

3. **Step 3: Actionable Remediation**:
   - Provide concrete replacement code (`fix`) and standards references (`references`).

## Severity Scale
- **CRITICAL**: Directly exploitable vulnerability, authentication bypass, credential leak, or fatal runtime/syntax error visible in code.
- **HIGH**: Exploitable flaw requiring preconditions (authenticated access, race condition, data corruption, resource leak).
- **MEDIUM**: Flaw with bounded blast radius, unhandled error state, or partially mitigated defect.
- **LOW**: Defense-in-depth, observability, or hardening improvement with no direct exploit path.

## Mandatory Finding Structure
Each finding in JSON MUST contain:
- `severity`: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
- `location`: "path/to/file.ext:start-end"
- `title`: Concise title
- `description`: Technical defect explanation and exploit scenario
- `fix`: Specific code fix
- `verification_criteria`: List of conditions confirming the defect
- `invalidation_criteria`: List of conditions disproving the defect
- `references`: List of CVE / CWE / RFC / NIST / SOC references

## Merge Recommendation
- **BLOCK**: Unmitigated CRITICAL findings.
- **REQUEST CHANGES**: Unresolved HIGH, MEDIUM, or LOW findings.
- **APPROVE**: Sound code with zero findings.
