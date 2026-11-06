# Tasks

## 1. Argo workflow waiting leaves the command (behavior)

- [x] 1.1 Write the failing tests of `await_workflow` on `cluster` and `clock`: a terminal phase returns at once, a running phase is polled until it turns terminal, a budget that ends raises `ArgoWorkflowTimeoutError`, a missing Workflow and a failed read raise their typed errors
  - Verification: `uv run devops ci test tests/argo/test_workflows.py`
- [x] 1.2 Add `argo/workflows.py` with `await_workflow` and `ArgoWorkflowTimeoutError`, call them from `commands/argo.py`, and remove `_await_workflow` and the alias `_is_not_found`
  - Verification: `uv run devops ci test tests/argo tests/commands/test_argo.py`
- [x] 1.3 Run the Argo CRD tests on the `cluster` fixture with no mock, no patch and no private import
  - Verification: `uv run devops ci test tests/argo/test_argo_crd.py`

## 2. Cloudflare record matching leaves the command (behavior)

- [x] 2.1 Write the failing tests of `find_matching_records` and `delete_dns_records` on the `web` fake: a match by name, by label, by apex and by ID, the type filter, the managed comment and `force`, and the targets that match nothing
  - Verification: `uv run devops ci test tests/cloudflare/test_dns.py`
- [x] 2.2 Add `cloudflare/dns.py`, call it from `commands/cloudflare.py`, delete the four private helpers, and move the two matching cases out of `tests/commands/test_cloudflare_commands.py`
  - Verification: `uv run devops ci test tests/cloudflare tests/commands/test_cloudflare_commands.py`

## 3. Tests run on the edge fakes (test-only edits)

- [x] 3.1 Add the fake support: `ClockFake.after_each_sleep`, `ProcessCall.extra_allowed_env`, `DockerEngineFake.script_every_run` and the Kubernetes API `fail`
  - Verification: `uv run devops ci test tests/core/test_clock_contract.py tests/core/test_process_contract.py tests/docker/test_engine_contract.py tests/k8s`
- [x] 3.2 Run the watcher tests on `clock` and the public interface
  - Verification: `uv run devops ci test tests/watchers`
- [x] 3.3 Run the Terraform cost tests on `process_fake`, `cli` and `mcp_dispatcher`, and the analysis commands through `cli`
  - Verification: `uv run devops ci test tests/tf tests/commands/test_tf_cost.py tests/ai/mcp/test_tf_cost_tools.py`
- [x] 3.4 Run the Cosign tests on `process_fake` and `keyring_store`, and the sign and verify commands through `cli`
  - Verification: `uv run devops ci test tests/docker/test_cosign.py tests/commands/test_docker_cosign.py`
- [x] 3.5 Run the workload sandbox tests on `docker_daemon`
  - Verification: `uv run devops ci test tests/docker/test_sandbox.py tests/commands/test_workload_sandbox.py`
- [x] 3.6 Run the engine tests on `dns`, `clock` and `cli`, read the clock seam in `docker/engine.py`, and split the file by behaviour
  - Verification: `uv run devops ci test tests/docker tests/commands/test_docker_cache.py`
- [x] 3.7 The seven files of the issue hold no patch site, no private import and no module-level `CliRunner`
  - Verification: `! git grep -n -e monkeypatch.setattr -e monkeypatch.setitem -e monkeypatch.delattr -e patch.object -e patch.dict -e "with patch" -e @patch -e CliRunner -e "import _" -- tests/argo/test_argo_crd.py tests/argo/test_workflows.py tests/tf tests/watchers tests/docker/test_cosign.py tests/docker/test_sandbox.py tests/docker/test_engine_endpoint.py tests/docker/test_engine_connection.py tests/docker/test_engine_projection.py tests/docker/test_engine_containers.py tests/docker/test_engine_facts.py tests/docker/test_engine_networks.py tests/docker/test_engine_build_cache.py tests/commands/test_docker_cosign.py tests/commands/test_workload_sandbox.py tests/commands/test_docker_cache.py tests/commands/test_tf_cost.py tests/cloudflare/test_dns.py`

## 4. Documents

- [x] 4.1 Add the error class to `docs/ERRORS.md` and point the active change 2554 at the new test file
  - Verification: `uv run devops ci docs`

## 5. Archive

- [x] 5.1 Archive the change
  - Verification: `uv run devops openspec archive 3751-infra-tests-on-edge-fakes`

## Workflow follow-up

- Item 6 of #1335 moves the Argo CD, PromQL and Grafana API calls out of `commands/` onto the HTTP fake.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
