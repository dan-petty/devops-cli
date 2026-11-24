# Tasks

## 1. Behavior

- [x] 1.1 Write failing test for Dockerfile build checks and dockerignore bytecode exclusion
  - Verification: `$ uv run pytest tests/invariants/test_service_image.py`
- [x] 1.2 Add check directive to Dockerfile and exclude bytecode in .dockerignore
  - Verification: `$ uv run pytest tests/invariants/test_service_image.py`

## 2. Documents

- [x] 2.1 Verify docs consistency
  - Verification: `$ uv run devops docs check`
