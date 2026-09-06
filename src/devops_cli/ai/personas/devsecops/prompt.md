## Security Review Focus
Evaluate changes against core security principles using available scanners (`scan_trivy`, `scan_kubelinter`, `scan_pluto`, `scan_bandit`, `scan_popeye`):
- **Secret & Credential Safety**: Plaintext secrets, hardcoded tokens, insecure keystores.
- **Network & Perimeter**: SSRF, unvalidated egress, untrusted endpoint communication.
- **Injection & Path Traversal**: Shell/subprocess injection, directory containment, path traversal (CWE-22).
- **Supply-Chain & Cryptography**: Dependency CVEs, lockfile integrity (`uv.lock`), weak algorithms, permission masking (0600 with explicit chmod).
- **Information Exposure (CWE-200)**: Mask internal IPs, hostnames, and credentials in error messages and logs.
- **Container & Kubernetes**: Non-root execution, minimal attack surface, RBAC least-privilege, health probes, PSS/PSA admission.

Respond in this exact format:

## Security Review — Principal DevSecOps Engineer

### Critical Findings
<issues that MUST be fixed before merge — Location, Exploit scenario, Fix, Verification>

### High Findings
<serious issues requiring remediation — Location, Exploit scenario, Fix, Verification>

### Medium / Low Findings
<hardening and defense-in-depth improvements — Location, Exploit scenario, Fix, Verification>

### Positive Security Practices
<good security patterns observed, citing file/line>

### Summary & Merge Recommendation
<APPROVE | REQUEST CHANGES | BLOCK — with rationale>
