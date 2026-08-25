# Knowledge Base: Gitleaks (Sub-Millisecond Secret Pre-Filter)

## 1. Overview & Purpose

`Gitleaks` is a fast, lightweight secret scanner designed to detect unencrypted secrets, API tokens, passwords, private keys, and high-entropy credentials in git repositories, directories, and files. In `devops-cli`, `gitleaks` operates as a pre-review static filter (`devops_cli.security.gitleaks`), catching credentials before LLM review and injecting findings into the `devsecops` persona session.

---

## 2. Usage Information & Architecture

- **Sub-Millisecond Secret Detection**: Scans files, commits, and diffs for hundreds of known secret patterns (AWS, GitHub, Slack, OpenAI, Stripe, RSA private keys).
- **Graceful Fallback**: When the `gitleaks` binary is not installed on the system, DevOps CLI executes a high-precision built-in regex secret detector.
- **Stage 2 Review Injection**: Automatically runs during Stage 2 review payload initialization (`_run_static_scanners`), pre-populating findings.
- **Agent & MCP Tool**: Exposes `scan_gitleaks` to AI personas and FastMCP servers.

---

## 3. Common & Advanced Commands

### DevOps CLI Gitleaks Invocations
```bash
# Scan workspace or target path for secrets
devops scan secrets .

# Scan specific directory with JSON output
devops scan gitleaks src/ --json

# Run dry-run simulated secret scan
devops scan secrets --dry-run
```

### Standard Gitleaks CLI Commands
```bash
# Detect secrets in working directory without git history
gitleaks detect --no-git --source .

# Scan git commits in a specific range
gitleaks detect --log-opts="main..HEAD"

# Output structured JSON findings
gitleaks detect --report-path gitleaks-report.json --report-format json
```

---

## 4. Best Practice Guidance

1. **Zero Plaintext Secrets**: Never store plaintext API keys, passwords, or tokens in source code or configuration files.
2. **Immediate Revocation**: Any secret caught by Gitleaks must be immediately rotated and revoked upstream.
3. **Pre-Commit Enforcement**: Run secret scans in pre-commit lifecycle hooks to prevent leaking credentials into git commit history.

---

## 5. Official References & Published Artifacts

- **Project Homepage**: [github.com/gitleaks/gitleaks](https://github.com/gitleaks/gitleaks)
- **Official Releases**: [github.com/gitleaks/gitleaks/releases](https://github.com/gitleaks/gitleaks/releases)
- **DevOps CLI Gitleaks Scanner**: [src/devops_cli/security/gitleaks.py](../../../../security/gitleaks.py)
