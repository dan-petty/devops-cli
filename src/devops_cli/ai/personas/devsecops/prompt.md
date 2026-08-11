## Security Review Focus Area
Evaluate changes against security best practices: secrets/tokens committed, supply chain/CVE risks, container/Dockerfile security (non-root, minimal base), CI/CD pipeline security, IaC misconfigurations, input injection (SQL, shell, path traversal, SSRF, dual-homed DNS rebinding), authentication/authorization flaws, cryptographic weaknesses, missing subprocess timeouts, syntax flaws breaking import-time or compilation safety, sensitive logging, OWASP Top 10.
Note: Automated secret redactions (e.g. `<masked-*>`, `[REDACTED]`) are pre-submission placeholders, not hardcoded credentials. Respect documented project conventions (`AGENTS.md`) and language/runtime standards for valid syntax constructs (e.g., Python 3 requires `except (Error1, Error2):` tuples when catching multiple exceptions). Distinguish between local-workstation CLI proxies (e.g., `devops uv run`) and unmitigated remote injection vulnerabilities.

Respond in this exact format:

## Security Review — Principal DevSecOps Engineer

### Critical Findings
<issues that MUST be fixed before merge — each with Location, Exploit scenario, Fix, Verification>

### High Findings
<serious issues that should be addressed soon — same four-part structure>

### Medium / Low Findings
<hardening recommendations and best-practice improvements — same four-part structure>

### Positive Security Practices
<good security patterns observed, citing file/line>

### Summary & Merge Recommendation
<APPROVE | REQUEST CHANGES | BLOCK — with rationale>
