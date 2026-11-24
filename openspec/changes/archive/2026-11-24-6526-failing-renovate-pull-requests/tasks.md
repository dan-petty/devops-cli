# Tasks

## 1. Renovate Configuration

- [x] 1.1 Add commitMessageTopic for SearXNG
  - Verification: `$ npx renovate-config-validator --strict .github/renovate.json`
- [x] 1.2 Restrict Node, Python, requires-python, and grafana-foundation-sdk versions
  - Verification: `$ npx renovate-config-validator --strict .github/renovate.json`

## 2. OpenSpec Requirements

- [x] 2.1 Shorten requirement texts in changes 3060 and 3429
  - Verification: `$ uv run devops openspec check`

## 3. Quality Gate

- [x] 3.1 Run CI quality gates
  - Verification: `$ uv run devops ci --check --skip test`
