# Tasks

## 1. Renovate config

- [x] 1.1 Write the failing tests: no digest pin of a `uses-with` input, one update for each security fix, and the semgrep hold with the Dashboard footer
  - Verification: `$ uv run devops ci test tests/core/test_renovate_config.py`
- [x] 1.2 Add the `uses-with` rule and `vulnerabilityAlerts.separateMajorMinor` to the preset, and the semgrep holds and the footer to the repository config
  - Verification: `$ uv run devops ci test tests/core/test_renovate_config.py`
- [x] 1.3 Validate both files with the Renovate validator in strict mode
  - Verification: `$ npx --yes --package renovate@44.239.1 renovate-config-validator --strict .github/renovate.json .github/renovate/base.json`

## Workflow follow-up

- #3988 takes the security fixes of `mcp` and `opentelemetry-api` into the semgrep lock, or records the time-limited ignore, and adds the advisory check of the tools lock files.
- #4909 measures the next run after the merge: the `trivy` and `uv` branches hold no `pinDigest` update, and no empty commit is logged.
