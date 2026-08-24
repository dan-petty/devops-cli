# Knowledge Base: Bandit (Python AST Static Security Analysis)

## 1. Overview & Purpose

Bandit is an open-source static code analysis tool designed to find common security issues in Python code. It processes Python source files, builds Abstract Syntax Trees (AST), and evaluates plugins against AST nodes to identify vulnerabilities such as hardcoded passwords, SQL injections, insecure cryptographic algorithms, unsafe shell executions, and unsafe deserialization. In `devops-cli`, Bandit is an enforced gate in `devops ci` and `devops release check`.

---

## 2. Usage Information & Architecture

- **AST Analysis Engine**: Parses Python code directly without executing it, avoiding arbitrary code execution risks during scanning.
- **CWE Mapping**: Categorizes findings by Common Weakness Enumeration (CWE) and severity (Low, Medium, High) / confidence (Low, Medium, High).
- **CI Quality Gate**: `devops ci` runs Bandit across all source files in `src/`, failing the quality gate if any high-confidence medium or high-severity vulnerabilities are found.
- **Implementation**: Programmatically integrated in `src/devops_cli/security/bandit.py`.

---

## 3. Common & Advanced Commands

### DevOps CLI Bandit Commands
```bash
# Run full CI quality gate including Bandit security scan
devops ci

# Run Bandit programmatically against target directory
devops scan security src/
```

### Standard & Advanced `bandit` Commands
```bash
# Scan entire Python source package recursively
bandit -r src/

# Scan with custom severity threshold (Medium and High only)
bandit -r src/ -ll

# Scan with custom confidence threshold (High confidence only)
bandit -r src/ -iii

# Exclude test directories or specific rules
bandit -r src/ -x tests/ --skip B608

# Generate structured JSON report
bandit -r src/ -f json -o bandit-report.json
```

### Key Bandit Test Identifiers
| Rule ID | Name | Description |
| :--- | :--- | :--- |
| **B105-B107** | Hardcoded Passwords | Detects hardcoded password strings or tokens. |
| **B301-B303** | Insecure Crypto/Hashes | Detects usage of MD5, SHA1, or weak ciphers. |
| **B324** | Insecure Hashlib | Flagging hashlib usage without `usedforsecurity=False`. |
| **B602** | Shell Injection | Detects `subprocess.Popen` or `subprocess.run` with `shell=True`. |
| **B608** | Hardcoded SQL Expressions | Detects SQL query strings constructed with formatting. |

---

## 4. Best Practice Guidance

1. **Never Use `shell=True`**: Always pass command arguments as explicit lists (e.g. `["kubectl", "get", "pods"]`) to prevent shell injection vulnerabilities.
2. **Explicit Hash Flags**: When computing non-cryptographic hashes (e.g. cache keys), pass `usedforsecurity=False` in Python 3.14+ to prevent Bandit alerts.
3. **Use `# nosec` with Justification**: If a false positive must be suppressed, annotate the specific line with `# nosec <RULE_ID>` and a clear design justification comment.
4. **Scan Pre-Commit**: Integrate Bandit into pre-commit hooks so developers receive immediate security feedback before pushing commits.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Zero Tolerance for High Severity**: CI builds must fail immediately if Bandit discovers high-severity security issues.
- **Keyring Token Management**: Never store API tokens as module-level constants in Python files; always resolve them dynamically via `keyring` or environment variables.

---

## 6. General Standards & Reference Guidelines

- **Configuration File**: Controlled via `pyproject.toml` (`[tool.bandit]`) or standard CLI options.
- **Python 3.14 Compatibility**: Supports all modern Python AST syntax constructs.

---

## 7. Official References & Published Artifacts

- **Project Homepage**: [bandit.readthedocs.io](https://bandit.readthedocs.io/)
- **Public Git Repository**: [github.com/PyCQA/bandit](https://github.com/PyCQA/bandit)
- **Official PyPI Package**: [pypi.org/project/bandit](https://pypi.org/project/bandit/)
- **DevOps CLI Bandit Scanner**: [src/devops_cli/security/bandit.py](../../../src/devops_cli/security/bandit.py)
