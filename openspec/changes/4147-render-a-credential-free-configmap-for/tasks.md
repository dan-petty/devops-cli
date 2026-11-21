# Tasks

## 1. Drop secret-named keys at any depth

Kind: behavior. Reads: `src/devops_cli/security/sanitizer.py`, `src/devops_cli/config/constants.py`, `tests/security/test_secret_redaction.py`, `tests/ai/client/test_url_credential_masking.py`, `tests/ai/mcp/test_mcp_tool_secrets.py`, `tests/ai/review/test_review_defenses_and_verification.py`, `tests/ai/test_review_finding_losses.py`, `tests/ai/test_review_prompt_guardrails.py`, `tests/commands/k8s/test_subsystem_containment_and_redaction.py`, `tests/commands/test_devcontainer.py`, `tests/review/test_review_prompt_adversaries.py`, `tests/roadmap/implement/test_roadmap_implement_step_repair.py`, `tests/roadmap/stage/test_roadmap_stage_round_log.py`, `tests/security/test_network_security.py`, `tests/security/test_private_host_masking.py`, `tests/security/test_redaction_properties.py`, `tests/security/test_runtime_input_guards.py`, `tests/telemetry/test_telemetry_llm_content.py`. Changes: `src/devops_cli/security/sanitizer.py`, `tests/security/test_secret_redaction.py`.
Adds: `drop_secret_named_keys`

- [ ] 1.1 Add a case in `tests/security/test_secret_redaction.py` named `test_drop_secret_named_keys_removes_each_credential_key_at_any_depth`, which drops a top-level github_token, a nested db_password and a secret inside a list, and keeps the non-credential keys with their values
  - Verification: `$ uv run devops ci test tests/security/test_secret_redaction.py` fails on the base
- [ ] 1.2 Add `drop_secret_named_keys(data)` to `src/devops_cli/security/sanitizer.py` beside `mask_secret_named_values`: a dict keeps each entry whose key `is_secret_parameter_name` does not match and recurses into the value, a list recurses into each item, and any other value returns unchanged. The new case in `tests/security/test_secret_redaction.py` covers a top-level `github_token`, a nested `db_password` and a `secret` inside a list, and asserts that the non-credential keys keep their values
  - Verification: `$ uv run devops ci test tests/security/test_secret_redaction.py` passes

## 2. Render the credential-free sandbox ConfigMap

Kind: behavior. Reads: `src/devops_cli/k8s/configmap.py`, `src/devops_cli/k8s/__init__.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/setting_keys.py`, `src/devops_cli/security/sanitizer.py`, `tests/k8s/test_k8s_configmap.py`, `tests/config/test_config_file_value_errors.py`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/k8s/configmap.py`, `src/devops_cli/k8s/__init__.py`, `tests/k8s/test_k8s_configmap.py`.
Adds: `CONST_K8S_DEVOPS_SANDBOX_CONFIGMAP`, `render_active_devops_sandbox_configmap`

- [ ] 2.1 Add a case in `tests/k8s/test_k8s_configmap.py` named `test_the_sandbox_config_map_drops_every_credential_key_and_keeps_its_name`, which renders the sandbox ConfigMap from a template with a top-level credential key and one nested under `ai`, walks every key of the inner config at any depth, and asserts the name, the namespace and the single data key
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_configmap.py` fails on the base
- [ ] 2.2 Add `CONST_K8S_DEVOPS_SANDBOX_CONFIGMAP: Final[str] = "devops-cli-config-sandbox"` beside `CONST_K8S_DEVOPS_CONFIGMAP` in `src/devops_cli/config/constants.py`. Add a keyword-only `drop_secret_keys` parameter to `render_devops_configmap_content` and `render_active_devops_configmap` in `src/devops_cli/k8s/configmap.py`: it replaces the parsed config with `drop_secret_named_keys` of it after the service block is set and before `Settings.model_validate` and `unknown_setting_keys`, so a credential key of the template leaves the config instead of failing as an unknown setting. Add `render_active_devops_sandbox_configmap(product_dir, settings=None)`: it renders with the drop, sets `metadata.name` to the new constant and returns the manifest with the one data key. Export it from `src/devops_cli/k8s/__init__.py` beside `render_active_devops_configmap`. The new case in `tests/k8s/test_k8s_configmap.py` writes a template with `github_token`, `ai.api_key`, `ai.db_password` and a `secret` under a task beside non-credential keys, renders it, asserts that those four keys are gone and that the non-credential keys keep their values, and asserts metadata.name, metadata.namespace and the single data key
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_configmap.py` passes

## 3. Apply, delete and name the sandbox ConfigMap in the devops stack

Kind: behavior. Reads: `src/devops_cli/commands/k8s/stack_lifecycle.py`, `tests/commands/k8s/test_k8s.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/ai/test_llm_pool_metrics.py`, `tests/commands/k8s/test_k8s_agents_manifests.py`, `tests/commands/k8s/test_k8s_devops_stack.py`, `tests/commands/k8s/test_k8s_networking.py`, `tests/commands/k8s/test_k8s_qdrant_security.py`, `tests/commands/k8s/test_subsystem_containment_and_redaction.py`, `tests/commands/test_k8s_manifest_dry_run.py`, `tests/invariants/test_architectural_invariants.py`. Changes: `src/devops_cli/commands/k8s/stack_lifecycle.py`, `tests/commands/k8s/test_k8s.py`.
Adds: `_render_sandbox_configmap`, `stdins_of`

- [ ] 3.1 Add a case in `tests/commands/k8s/test_k8s.py` named `test_deploy_stack_applies_the_credential_free_sandbox_config_map`, which deploys the devops stack on a native cluster and asserts that the second stdin manifest is the sandbox ConfigMap with no credential key
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py` fails on the base
- [ ] 3.2 Add `_render_sandbox_configmap(product)` to `src/devops_cli/commands/k8s/stack_lifecycle.py` beside `_render_devops_configmap`, with the same error exit. In `deploy_stack`, render it when devops is among the selected stacks and apply it right after devops-cli-config on the native path and on the Argo CD-managed path, so the first stdin manifest stays devops-cli-config. Add the sandbox ConfigMap to the deploy dry-run details as devops/devops-cli-config-sandbox, with no value, and add its name to the teardown dry run. In `teardown_stack`, delete ConfigMap devops-cli-config-sandbox with --ignore-not-found beside the existing delete. Add `stdins_of` to the fake cluster of the test module, which returns every stdin payload of a command, and extend `test_deploy_stack_on_a_native_cluster_applies_the_rendered_config_map_and_no_file_of_it`, `test_deploy_stack_on_argo_cd_applies_the_config_map_and_sets_hosts_from_each_applications_revision`, `test_teardown_stack_devops_deletes_the_config_map_deploy_stack_rendered` and `test_deploy_stack_dry_run_reports_the_config_map_and_host_overrides_and_runs_nothing`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py` passes

## 4. Document the sandbox ConfigMap at deploy time

Kind: other. Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [ ] 4.1 Add the row of ConfigMap devops-cli-config-sandbox to the Homelab Values at Deploy Time table of `k8s/README.md` beside the row of devops-cli-config, and say that deploy-stack renders it from the active config with every credential-named key removed and that teardown-stack deletes it
  - Verification: `$ uv run devops ci docs` passes
- [ ] 4.2 Edit `k8s/README.md` to list the sandbox ConfigMap in the Homelab Values at Deploy Time table and to name the command that renders and deletes it
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: `devops k8s deploy-stack --stack devops` SHALL render ConfigMap `devops-cli-config-sandbox` from `config.yaml`, with every key that holds a credential removed.
- Group 2: A test SHALL assert that the rendered ConfigMap holds no key that holds a token, a key or a password.
- Group 2: The CronJob of #4003 SHALL mount that ConfigMap with no change to its manifest.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
