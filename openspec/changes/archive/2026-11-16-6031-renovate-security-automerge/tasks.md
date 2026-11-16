# Tasks

## 1. Behavior

- [x] 1.1 Write a test that fails unless the one automerge is the security fix of this repository
  - Verification: `$ uv run pytest tests/core/test_renovate_config.py`
- [x] 1.2 Set `vulnerabilityAlerts` automerge in `.github/renovate.json`
  - Verification: `$ npx --package renovate@44.239.1 renovate-config-validator .github/renovate.json`

## 2. Documents

- [x] 2.1 Name the exception in `AGENTS.md`, `docs/SDLC.md` and `docs/CLUSTER.md`
  - Verification: `$ uv run devops openspec check`
