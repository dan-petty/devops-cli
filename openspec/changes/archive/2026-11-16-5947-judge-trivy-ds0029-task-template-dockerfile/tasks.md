# Tasks

## 1. Behavior

- [x] 1.1 Add unit test in `tests/security/test_trivy_config_ignore.py` for the harbor DS-0029 entry
  - Verification: `$ uv run pytest tests/security/test_trivy_config_ignore.py -k test_the_repository_ignore_file_holds_the_harbor_entry`
- [x] 1.2 Add the DS-0029 ignore entry to `.trivyignore.yaml`
  - Verification: `$ uv run pytest tests/security/test_trivy_config_ignore.py`

## 2. OpenSpec

- [x] 2.1 Update capability spec `trivy-config-alerts` with the new requirement
  - Verification: `$ uv run devops openspec validate`
