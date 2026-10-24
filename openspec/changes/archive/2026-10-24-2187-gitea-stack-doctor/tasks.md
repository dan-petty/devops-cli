# Tasks

## 1. The checks of the live Gitea stack

- [x] 1.1 Write the failing tests of each check's pass and fail, the delete of the temporary repository, the password, the dry run and the command in `tests/test_gitea_doctor.py`, and see them fail with `uv run devops ci test tests/test_gitea_doctor.py` (no module `devops_cli.k8s.gitea_doctor` on `origin/main`)
- [x] 1.2 Add `StubWeb.serve` to the shared HTTP fake in `tests/web_fakes.py`; verify with `uv run devops ci test tests/test_http_broker.py tests/test_install_tools.py tests/test_github_session.py tests/test_http_egress.py`
- [x] 1.3 Add `src/devops_cli/k8s/gitea_doctor.py`, `DoctorCheck` and the field `checks` of `DoctorReport` in `src/devops_cli/models/k8s.py`, `DoctorCheckError` in `src/devops_cli/exceptions/k8s.py`, `get_gitea_admin_password` in `src/devops_cli/config/settings.py`, and the constants and defaults; use `CONST_K8S_GITEA_ADMIN_USER` in the row `gitea/gitea-admin` of `src/devops_cli/k8s/cluster_secrets.py`; verify with `uv run devops ci test tests/test_gitea_doctor.py tests/test_k8s_doctor.py tests/test_k8s_push_secrets.py tests/test_k8s_gitea.py tests/test_secret_resolution.py tests/test_exceptions.py tests/test_k8s_models.py`

## 2. The command and the MCP tool

- [x] 2.1 Add `--stack` to `devops k8s doctor` in `src/devops_cli/commands/k8s/diagnostics.py` (the table, the JSON and YAML output, the dry-run plan and the exit codes) with its help text in `src/devops_cli/lang/en/help.py`, and set `readOnlyHint: false` on the MCP tool `k8s_doctor` in `CONST_MCP_EXPOSURE_TABLE`; verify with `uv run devops ci test tests/test_gitea_doctor.py tests/test_fastmcp_contracts.py tests/test_cli_format_adoption.py tests/test_mcp.py`

## 3. Documentation

- [x] 3.1 In the Gitea section of `k8s/README.md`, add rollout step 5 and the section `Stack checks`, which name the command in place of the hand-run lines; name the command in `src/devops_cli/ai/knowledge_base/devops_cli/tasks/k8s_stack_deployment.md`; verify with `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## Workflow follow-up

- Pending a person: delete the key `ai.vllm_url`, which v0.2.34 removed, from the workspace `config.yaml`. Since #2168, the settings refuse it, so `load_settings` fails, and the `clone-url` check fails with that reason, which names `devops config unset ai.vllm_url`, until then.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
