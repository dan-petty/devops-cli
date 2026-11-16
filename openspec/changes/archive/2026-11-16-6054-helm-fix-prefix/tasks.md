# Tasks

## 1. Renovate configuration

- [x] 1.1 Add the helm rule and the prefix of the `dcgm-exporter` group to `.github/renovate.json`
  - Verification: `$ uv run devops ci test tests/core/test_renovate_config.py`
- [x] 1.2 Validate both files with the validator of the Renovate version of the CronJob
  - Verification: `$ npx --yes --package renovate@44.239.1 renovate-config-validator --strict --no-global .github/renovate.json .github/renovate/base.json`

## 2. Documents

- [x] 2.1 Name the prefix and the checks that a chart update still fails in `docs/SDLC.md`
  - Verification: `$ uv run devops ci docs`
