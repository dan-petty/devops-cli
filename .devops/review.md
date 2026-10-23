# Review Guards for devops-cli

Each bullet states what a review of this repository must not flag. The function `nearest_review_conventions` reads this file.

- **Context-Aware Documentation, Examples & Test Evaluation**:
  - Never flag documentation, architectural guides, security tutorials, knowledge base articles, prompt benchmarks, test assertions/fixtures, test mocks, sample configuration files (`*.example.*`, `*.sample.*`, `*.env.example`), or comments describing vulnerabilities in the context of avoiding or mitigating them.
  - Infrastructure-as-Code operator outputs (`outputs.tf`) must not be flagged as remote command injection.
- **Ground-Truth Scope & Variable Verification (Zero False NameErrors)**: Analysis stages MUST NOT declare a variable, constant, or imported symbol as undefined (`NameError`) without verifying the entire enclosing function, class, or module scope. If a symbol was imported, assigned, or passed as a parameter in active scope or outer closure, the finding is a hallucination and MUST NOT be reported.
- **Console Path Output vs Information Exposure (CWE-200)**: Printing local working directories, review target paths, or artifact locations to stdout/stderr is standard CLI UX and does NOT constitute CWE-200 Information Exposure, which applies to secrets, credentials, or private keys leaked to unauthenticated logs or external responses.
- **Safe Introspection vs Remote Code Execution (RCE)**: Introspecting attributes on internal typed Pydantic models via `getattr(model, field, default)` or `hasattr` is safe Python idiom and MUST NOT be flagged as insecure deserialization or arbitrary code execution.
