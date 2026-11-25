# Tasks

## 1. Ignore Entry

Kind: other.

- [x] 1.1 Add the dated `DS-0002` ignore entry for `.venv/lib/python3.14/site-packages/harbor/cli/template-task/pytest-tests/Dockerfile` (`expired_at: 2026-11-28`) to `.trivyignore.yaml`
  - Verification: `$ uv run devops scan report --scanner trivy-config`

## 2. Quality Gates

Kind: other.

- [x] 2.1 Verify OpenSpec checks and local CI gates pass
  - Verification: `$ uv run devops openspec check`
