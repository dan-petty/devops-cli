# Tasks

## 1. Read each config file as YAML 1.2

Kind: behavior. Reads: `src/devops_cli/config/round_trip.py`. Changes: `src/devops_cli/config/yaml_errors.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/write_history.py`, `src/devops_cli/config/round_trip.py`, `src/devops_cli/commands/config.py`, `src/devops_cli/k8s/configmap.py`, `src/devops_cli/crypto/ssh_keys.py`, `tests/config/test_config_file_yaml_1_2.py`, `tests/config/test_config_yaml_load_errors.py`, `tests/config/test_config_file_that_is_not_yaml.py`, `tests/config/test_config_write_history.py`, `tests/commands/test_config.py`, `tests/commands/test_config_audit_keys.py`, `tests/k8s/test_k8s_configmap.py`, `tests/crypto/test_ssh.py`.

- [x] 1.1 Write the failing tests: a bare `off` and `on` for `roadmap.intake.jev`, a bare `off` in `roadmap.decisions`, a YAML bool, and a duplicate key through the settings load; `devops config set` of `roadmap.intake.jev off`, `search.language no` and `k8s.context 12:30`; the audit record of a write; `devops config audit-keys` of a credential `no`; the ConfigMap render of a bare `off`; the SSH key prefix `no` of a project config file.
  - Verification: `$ uv run devops ci test tests/config/test_config_file_yaml_1_2.py tests/commands/test_config.py tests/config/test_config_write_history.py tests/commands/test_config_audit_keys.py tests/k8s/test_k8s_configmap.py tests/crypto/test_ssh.py`
- [x] 1.2 Add `parse_config_yaml` and `yaml_load_errors` to `config/yaml_errors.py`, make `load_yaml` catch the errors of ruamel.yaml, and remove its `errors` parameter. Read the config file with `parse_config_yaml` in `config/settings.py`, `config/write_history.py`, `commands/config.py`, `k8s/configmap.py` and `crypto/ssh_keys.py`. Remove `_LOAD_ERRORS` of `config/round_trip.py` and `_AUDIT_READ_ERRORS` of `commands/config.py`. Move the load error tests from PyYAML to the YAML 1.2 reader.
  - Verification: `$ uv run devops ci test tests/config/test_config_file_yaml_1_2.py tests/commands/test_config.py tests/config/test_config_write_history.py tests/commands/test_config_audit_keys.py tests/k8s/test_k8s_configmap.py tests/crypto/test_ssh.py tests/config/test_config_yaml_load_errors.py tests/config/test_config_file_that_is_not_yaml.py`

## 2. Documents

Kind: documents. Changes: `src/devops_cli/docs/generator.py`, `docs/CONFIGURATION.md`, `docs/roadmap/intake.md`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pyyaml_jinja2.md`.

- [x] 2.1 State in the generated configuration reference (`docs/generator.py`, `docs/CONFIGURATION.md`) and in `docs/roadmap/intake.md` that a config file is read as YAML 1.2, so a bare `off`, `on`, `yes` or `no` is a string.
  - Verification: `$ uv run devops docs generate --check`
- [x] 2.2 State in the knowledge page of PyYAML that PyYAML reads YAML 1.1, that `parse_config_yaml` reads each config file as YAML 1.2, and that `load_yaml` has no `errors` parameter.
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
