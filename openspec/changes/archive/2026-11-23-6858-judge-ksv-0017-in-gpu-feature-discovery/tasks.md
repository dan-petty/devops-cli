# Tasks

## 1. Ignore Entry

- [x] 1.1 Update `.trivyignore.yaml` with `expired_at: 2026-11-26` for KSV-0017, KSV-0121, and KSV-0118
  - Verification: `$ uv run devops scan report --scanner trivy-config`

## 2. Quality Gate

- [x] 2.1 Run local quality gate checks
  - Verification: `$ uv run devops openspec check`
