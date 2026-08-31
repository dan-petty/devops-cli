# Code Library: Bandit & Actionlint (Security & CI Workflow Analysis)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [bandit.readthedocs.io](https://bandit.readthedocs.io/) • [github.com/rhysd/actionlint](https://github.com/rhysd/actionlint) |
| **Public Git Repository** | [github.com/PyCQA/bandit](https://github.com/PyCQA/bandit) • [github.com/rhysd/actionlint](https://github.com/rhysd/actionlint) |
| **Official PyPI Packages** | `bandit==1.9.4`, `actionlint-py==1.7.12.24` |
| **DevOps CLI Integration** | [`src/devops_cli/commands/ci.py`](file:///workspaces/devops-cli/src/devops_cli/commands/ci.py) • [`src/devops_cli/security/`](file:///workspaces/devops-cli/src/devops_cli/security/) |

---

## 2. General Information & Architecture

**Bandit** is an AST-based static security analyzer designed to find common security issues (CWEs) in Python code. **Actionlint** is a dedicated static linter for GitHub Actions workflow files (`.github/workflows/*.yaml`).

In `devops-cli`:
- **Python Security Quality Gate**: `bandit` audits Python source files for insecure cryptographic algorithms, hardcoded passwords, shell injections, unsafe YAML loads, and insecure subprocess invocations.
- **Workflow Security Gate**: `actionlint` inspects GitHub Actions workflow syntax, expression contexts, untrusted pull request triggers, and script injection risks (`${{ github.event... }}`).

---

## 3. Comparable Projects & Tradeoffs

| Tool | Strengths | Weaknesses | Why `devops-cli` Chose Bandit + Actionlint |
| :--- | :--- | :--- | :--- |
| **`bandit`** | Fast AST scanning, Python-specific vulnerability rules (CWE checks), low false-positive rate. | Limited to Python AST rules. | **Selected**: The standard Python static security scanner required in production CI gates. |
| **`actionlint`** | Dedicated GitHub Actions AST parser, checks expression syntax and context variables, detects script injection vectors. | Specific to GitHub Actions. | **Selected**: Essential for preventing CI workflow compromise and unauthorized secret extraction. |
| **`semgrep`** | Polyglot static analysis engine. | Requires downloading external rulesets. | Used in addition to Bandit for broad polyglot scans. |
| **`checkov`** | Policy-as-code scanner for IaC and workflows. | Slower initialization than standalone actionlint. | Both tools work synergistically. |

---

## 4. Key Concepts & Core Patterns

1. **AST Node Inspection**: Bandit builds Python AST trees and evaluates nodes against security test plugins (e.g. `B602` for `shell=True`, `B506` for unsafe YAML load).
2. **Actionlint Expression Verification**: Verifies that GitHub Actions expressions (`${{ ... }}`) reference valid context properties and are properly enclosed in quotes.
3. **Automated CI Integration**: Executed automatically during `devops ci` as checks 8 and 9.

---

## 5. Common & Advanced Usage Examples

### Running Security Audits via CLI
```bash
# Execute Bandit security scan across Python source modules
uv run bandit -r src/

# Execute Actionlint against all GitHub Actions workflow definitions
uv run actionlint
```

---

## 6. Best Practices & Security Standards

1. **Zero Shell=True Subprocesses**: Never use `shell=True` in `subprocess.run()`; always pass command argument lists (`["kubectl", "get", "pods"]`).
2. **No Untrusted Workflow Injections**: Always pass GitHub context values via environment variables rather than direct bash script interpolations:
   ```yaml
   # Safe practice:
   env:
     PR_TITLE: ${{ github.event.pull_request.title }}
   run: |
     echo "Title: $PR_TITLE"
   ```
