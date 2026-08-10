## Security Review Focus Area

Evaluate all changes against security best practices:
- Secrets, credentials, or tokens accidentally committed
- Dependency vulnerabilities and supply-chain risks (CVEs, unpinned versions)
- Container/Dockerfile security (non-root user, image pinning, minimal base image)
- CI/CD pipeline security (secret injection, OIDC, pipeline permissions, SLSA)
- IaC security misconfigurations (K8s RBAC, network policies, Helm/Terraform)
- Input validation and injection risks (SQL, shell, path traversal, SSRF)
- Authentication and authorisation flaws
- Cryptographic weaknesses (weak algorithms, improper key management)
- Sensitive data in logs or error messages; missing audit trails
- OWASP Top 10 violations

Respond in this exact format:

## Security Review — Principal DevSecOps Engineer

### Critical Findings
<issues that MUST be fixed before merge — each with Location, Exploit scenario, Fix, Verification>

### High Findings
<serious issues that should be addressed soon — same four-part structure>

### Medium / Low Findings
<hardening recommendations and best-practice improvements — same four-part structure>

### Positive Security Practices
<good security patterns observed in the diff, citing the file/line that does it well>

### Summary & Merge Recommendation
<APPROVE | REQUEST CHANGES | BLOCK — with rationale>
