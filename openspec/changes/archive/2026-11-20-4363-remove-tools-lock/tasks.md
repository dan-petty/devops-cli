# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: tools on PATH only (`semgrep`, `ruff`, `ansible-runner`), a missing `ruff` before a model job, the installed kubectl version, the recorded tool versions of the analysis, the knowledge base and the profile, `unknown` for a native tool, and an old plan record that must be planned again
  - Verification: `$ uv run devops ci test tests/infra tests/k8s/test_k8s_doctor.py tests/review tests/ai/review/test_review_profile.py tests/commands/test_review_rules_pack.py tests/commands/test_infra_apply.py`
- [x] 1.2 Delete `devops install-tools`, `src/devops_cli/tools_lock`, the lock audit rows and the readers of the lock
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py tests/commands/test_dependency_audit.py tests/research tests/security tests/core`

## 2. Workflows, Renovate and documents

- [x] 2.1 Scan the cloudflared image in the third-party image scan, and remove the Renovate managers and rules of the lock
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 2.2 Update the documents and regenerate the generated ones
  - Verification: `$ uv run devops ci docs`
