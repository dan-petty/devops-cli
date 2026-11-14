# Tasks

## 1. Add the dated KSV-0017 ignore entry and its test

Kind: other. Reads: `SECURITY.md`, `k8s/gpu-feature-discovery/daemonset.yaml`, `tests/security/test_trivy_config_ignore.py`, `.trivyignore`. Changes: `.trivyignore.yaml` (new), `tests/security/test_trivy_config_ignore.py`.

- [ ] 1.1 Add `test_the_repository_ignore_file_holds_the_privileged_gpu_entry` to `tests/security/test_trivy_config_ignore.py` first: it loads `.trivyignore.yaml` with `yaml.safe_load`, finds the `misconfigurations` entry with the `id` `KSV-0017` and the path `k8s/gpu-feature-discovery/daemonset.yaml`, and asserts a `statement` that holds `#5646` and an `expired_at` that parses as a date. Then create `.trivyignore.yaml` with that entry, a `statement` that names the privileged GPU device and sysfs access of GFD v0.16.2 and #5646, and `expired_at` set to the day of the commit plus 3 days
  - Verification: `$ uv run devops ci test tests/security/test_trivy_config_ignore.py` passes
