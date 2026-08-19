## Security Review Focus Area
Evaluate changes against security best practices:
- Secret leaks, plaintext tokens, and credential handling (enforce OS Keyring).
- SSRF, private network bypass, and unvalidated outbound requests (enforce IP validation).
- Injection vulnerabilities (shell/subprocess command injection, flag injection, path traversal, SQLi).
- Dependency and supply-chain CVE vulnerabilities.
- Cryptographic flaws (weak algorithms, insecure key generation, improper permissions).
- Container & CI/CD security (non-root execution, minimal attack surface, secret masking).
- OWASP Top 10 vulnerabilities and defensive coding standards.

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
