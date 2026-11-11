# Tasks

## 1. Behavior

- [x] 1.1 Change `tests/core/test_renovate_config.py`: the SearXNG note names no tag age, and the Renovate file sets no `minimumReleaseAge` and does not extend `config:best-practices`
  - Verification: `$ uv run devops ci test tests/core/test_renovate_config.py`
- [x] 1.2 Remove the 14-day age from the SearXNG rule of `.github/renovate.json`
  - Verification: `$ uv run devops ci test tests/core/test_renovate_config.py`

## 2. Documents

- [x] 2.1 Add the bullet **Dependency Versions** to `CONTRIBUTING.md`, section 1, and link to it from `SECURITY.md` and the SearXNG pin steps of `k8s/README.md`
  - Verification: `$ uv run devops ci test tests/invariants/`
