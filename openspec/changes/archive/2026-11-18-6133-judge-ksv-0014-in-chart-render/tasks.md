# Tasks

## 1. Ignore Entry

- [x] 1.1 Add KSV-0014 ignore entry for `tests/fixtures/image_pins/chart_render.yaml` to `.trivyignore.yaml`
  - Verification: `$ trivy config tests/fixtures/image_pins/chart_render.yaml --ignorefile .trivyignore.yaml --severity HIGH,CRITICAL`

## 2. Quality Gate

- [x] 2.1 Run local quality gate checks
  - Verification: `$ uv run devops openspec check`
