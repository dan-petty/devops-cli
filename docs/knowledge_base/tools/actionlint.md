# Knowledge Base: actionlint (GitHub Actions Static Workflow Linter)

## 1. Overview & Purpose

`actionlint` is a static checker for GitHub Actions workflow files (`.github/workflows/*.yml`). Written in Go, it parses workflow YAML files, verifies GitHub Actions syntax schemas, validates shellcheck expressions, checks action inputs/outputs against official action repositories, and flags untrusted code execution risks. In `devops-cli`, `actionlint` is an enforced gate in `devops ci` and `devops release check`.

---

## 2. Usage Information & Architecture

- **Static Workflow Analysis**: Catches syntax errors, invalid context expressions (`${{ github.event... }}`), and missing matrix variables before pushing commits to remote branches.
- **Embedded ShellCheck**: Analyzes inline `run:` shell scripts for syntax mistakes, unquoted variables, and potential shell injection vulnerabilities.
- **CI Quality Gate**: `devops ci` executes `actionlint` across all files in `.github/workflows/`.
- **Pre-commit Integration**: Configured in `.pre-commit-config.yaml` to run automatically on git commit.

---

## 3. Common & Advanced Commands

### DevOps CLI Actionlint Invocations
```bash
# Run full CI quality gate including actionlint workflow validation
devops ci

# Run actionlint directly within the devcontainer
actionlint
```

### Standard & Advanced `actionlint` Commands
```bash
# Lint all workflows under .github/workflows/
actionlint

# Lint a specific workflow file with verbose error messages
actionlint .github/workflows/ci.yml

# Lint workflow with custom ShellCheck options
actionlint -shellcheck=shellcheck

# Output findings in JSON format for automated reporting
actionlint -format '{{json .}}'
```

---

## 4. Best Practice Guidance

1. **Pin Action SHAs**: Pin third-party GitHub Actions to immutable full commit SHAs (`uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2`) rather than floating tags.
2. **Quote Shell Variables**: Inside `run:` scripts, quote all shell variables (`"$MY_VAR"`) to satisfy embedded shellcheck rules.
3. **Validate Matrix Combinations**: Ensure `matrix:` configurations define valid Python versions (`"3.14"`) and OS platforms (`ubuntu-latest`).
4. **Use Explicit Permissions**: Declare least-privilege `permissions:` blocks at both the workflow and job level (e.g. `contents: read`, `pull-requests: write`).

---

## 5. Security Recommendations & Zero-Trust Policies

- **Prevent Expression Injections**: Never concatenate untrusted user input directly into inline `run:` scripts (e.g. `${{ github.event.pull_request.title }}`). Pass untrusted data via environment variables (`env: PR_TITLE: ${{ github.event.pull_request.title }}`).
- **Restrict Secret Access**: Restrict workflow access to secrets using GitHub Actions environment protection rules.

---

## 6. General Standards & Reference Guidelines

- **File Location**: Store workflows exclusively under `.github/workflows/*.yml` or `.github/workflows/*.yaml`.
- **Exit Code**: Exit code `0` on clean workflows; exit code `1` when syntax or shellcheck errors are found.

---

## 7. Official References & Published Artifacts

- **Project Homepage & Repo**: [github.com/rhysd/actionlint](https://github.com/rhysd/actionlint)
- **Official Releases**: [github.com/rhysd/actionlint/releases](https://github.com/rhysd/actionlint/releases)
- **DevOps CLI CI Gate**: [src/devops_cli/commands/ci.py](file:///workspaces/devops-cli/src/devops_cli/commands/ci.py)
