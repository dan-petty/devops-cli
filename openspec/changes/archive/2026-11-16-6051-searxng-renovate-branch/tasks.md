# Tasks

## 1. Renovate configuration

- [x] 1.1 Add the SearXNG rule with `groupName` and `dependencyDashboardApproval` at the end of the package rules, and remove the approval test that reads `renovate.json`
  - Verification: `$ uv run devops ci test tests/core/test_renovate_config.py`
- [x] 1.2 Validate both files with the validator of the Renovate version of the CronJob
  - Verification: `$ npx --yes --package renovate@44.239.1 renovate-config-validator --strict --no-global .github/renovate.json .github/renovate/base.json`

## 2. Documents

- [x] 2.1 Describe the approval and the own branch in `docs/CLUSTER.md`
  - Verification: `$ uv run devops ci docs`
