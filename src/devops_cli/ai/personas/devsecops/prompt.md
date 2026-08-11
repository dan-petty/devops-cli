## Security Review Focus Area
Evaluate changes against security best practices: secrets/tokens committed, supply chain/CVE risks, container/Dockerfile security (non-root, minimal base), CI/CD pipeline security, IaC misconfigurations, input injection (SQL, shell, path traversal, SSRF, dual-homed DNS rebinding), authentication/authorization flaws, cryptographic weaknesses, missing subprocess timeouts, unparenthesized exception tuples breaking import-time safety, sensitive logging, OWASP Top 10.
Note: `<masked-*>` placeholders are automated pre-submission secret redactions by `devops-cli`. Parenthesized exception tuples `except (E1, E2):` are valid Python 3.14+ syntax. `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true` is an intentional opt-in for local LLM inference.

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
