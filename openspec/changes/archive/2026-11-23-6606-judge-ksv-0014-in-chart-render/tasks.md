# Tasks

## 1. Fixture & Suppression Fix

- [x] 1.1 Add restrictive security context to `tests/fixtures/image_pins/chart_render.yaml`
  - Verification: `$ trivy config tests/fixtures/image_pins/chart_render.yaml`
- [x] 1.2 Remove obsolete suppressions for `chart_render.yaml` from `.trivyignore.yaml`
  - Verification: `$ uv run devops scan report --scanner trivy-config`

## 2. Test Verification

- [x] 2.1 Run test suite using the fixture
  - Verification: `$ uv run pytest tests/k8s/test_image_pins.py`

## 3. Quality Gate

- [x] 3.1 Run local quality gate checks
  - Verification: `$ uv run devops openspec check`
