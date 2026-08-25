# Knowledge Base: Semgrep (Multilingual Static AST Pattern Matcher)

## 1. Overview & Purpose

`Semgrep` is a fast, open-source static analysis tool for searching code, enforcing security standards, and finding bugs at build and review time. Unlike regex searchers, Semgrep understands code syntax trees (ASTs) across Python, Go, TypeScript, Java, C#, Terraform, Docker, and Kubernetes YAML. In `devops-cli`, `semgrep` operates as a static analyzer (`devops_cli.security.semgrep`), injecting deterministic findings into `devsecops` and `qa` review stages.

---

## 2. Usage Information & Architecture

- **Semantic AST Matching**: Matches code patterns syntactically rather than through fragile text or regex matching.
- **Multilingual Support**: Supports 30+ languages and frameworks with official curated rule registries (`p/default`, `p/security-audit`, `p/owasp-top-ten`, `p/python`, `p/golang`).
- **DevOps Review Pipeline Integration**: Pre-filters static bugs and injects findings into Stage 2 review sessions (`_run_static_scanners`).
- **CLI Subcommand**: `devops scan semgrep` / `devops scan sast`.

---

## 3. Common & Advanced Commands

### DevOps CLI Semgrep Invocations
```bash
# Run Semgrep AST scan on current workspace with default rules
devops scan semgrep

# Scan with custom security ruleset and JSON output
devops scan sast src/ --config p/security-audit --json

# Run dry-run simulated AST scan
devops scan semgrep --dry-run
```

### Standard Semgrep CLI Commands
```bash
# Run Semgrep scan using default auto configuration
semgrep scan --config auto

# Scan specific directory using OWASP Top 10 rules
semgrep scan --config p/owasp-top-ten src/

# Run Semgrep and output JSON findings
semgrep scan --json --quiet src/
```

---

## 4. Best Practice Guidance

1. **Leverage Standard Registries**: Use established community rulesets (`p/default`, `p/security-audit`) rather than ad-hoc custom rules where possible.
2. **Deterministic Triaging**: Review findings produced by Semgrep have verified AST line ranges (`location="filename:n-n"`) and concrete rule descriptors.
3. **Continuous Enforcement**: Integrate Semgrep checks in CI pipelines to prevent merging known antipatterns into release branches.

---

## 5. Official References & Published Artifacts

- **Project Homepage**: [semgrep.dev](https://semgrep.dev/)
- **Official GitHub Repo**: [github.com/semgrep/semgrep](https://github.com/semgrep/semgrep)
- **DevOps CLI Semgrep Scanner**: [src/devops_cli/security/semgrep.py](../../../../security/semgrep.py)
