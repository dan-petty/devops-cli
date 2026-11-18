# Tasks

## 1. Ignore Entry

- [x] 1.1 Add KSV-0014 ignore entry for `tests/fixtures/prompt_adversaries/kubernetes_adversary.yaml` to `.trivyignore.yaml`
  - Verification: `$ trivy config tests/fixtures/prompt_adversaries/kubernetes_adversary.yaml --ignorefile .trivyignore.yaml --severity HIGH,CRITICAL`

## 2. Quality Gate

- [x] 2.1 Run local quality gate checks
  - Verification: `$ uv run devops openspec check`
