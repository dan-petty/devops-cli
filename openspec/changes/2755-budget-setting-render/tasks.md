# Tasks

## 1. The ConfigMap renderer

- [ ] 1.1 Add failing tests in `tests/test_k8s_configmap.py`: the rendered `service` section holds `github_requests_per_hour: 2000` when the active settings set it, holds none for the default, and `render_devops_configmap_content` writes a given value
  - Verification: `uv run devops ci test tests/test_k8s_configmap.py` fails on the base
- [ ] 1.2 Add the parameter to `_service_block`, `render_devops_configmap_content` and `render_active_devops_configmap` in `k8s/configmap.py`
  - Verification: `uv run devops ci test tests/test_k8s_configmap.py`
- [ ] 1.3 Run `uv run ruff check`, `uv run ruff format --check` and `uv run mypy --strict` on the changed files
  - Verification: `uv run devops ci lint`

## 2. The declaration and the documents

- [ ] 2.1 Add failing tests: the variable `DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR` in `tests/test_config_declarations.py`, and the numeric cases (`2000` valid, `0`, `-1`, `x` refused) in `tests/test_config_field_validation.py`
  - Verification: `uv run devops ci test tests/test_config_declarations.py tests/test_config_field_validation.py` fails on the base
- [ ] 2.2 Mark the field with `Variable()` and give it a description in `config/settings.py`
  - Verification: `uv run devops ci test tests/test_config_declarations.py tests/test_config_field_validation.py`
- [ ] 2.3 Run `uv run devops docs generate --sync-readme`, and write in `k8s/README.md` the owner's commands (`devops config set service.github_requests_per_hour <n>`, then `devops k8s deploy-stack --stack devops`)
  - Verification: `uv run devops ci docs`

## 3. The alert

- [ ] 3.1 Add failing promtool cases in `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` (limit 500: 600 fires, 400 quiet; limit 2000: 900 quiet, 1900 fires; the limit series with its own `instance` and `pod` labels) and update the expression in `tests/test_k8s_monitoring_alerting.py`
  - Verification: `uv run devops ci test tests/test_k8s_monitoring_alerting.py` fails on the base
- [ ] 3.2 Change the rule and its comment in `k8s/monitoring/prometheus-values.yaml`; update the alert row, the Go-live check and the settings row in `k8s/README.md`
  - Verification: `uv run devops ci test tests/test_k8s_monitoring_alerting.py` (promtool installed with `devops install-tools --tool promtool`)
- [ ] 3.3 Run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: run `devops config set service.github_requests_per_hour 2000`, then `devops k8s deploy-stack --stack devops`, and read `devops_cli_service_budget_limit_requests` (2000).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
