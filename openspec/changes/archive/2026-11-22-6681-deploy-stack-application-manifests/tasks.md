# Tasks

## 1. deploy-stack applies the builds of the path sources of the Applications

Kind: behavior. Reads: `src/devops_cli/k8s/app_render.py`, `src/devops_cli/k8s/app_sources.py`, `src/devops_cli/k8s/argocd_gate.py`, `src/devops_cli/k8s/template.py`, `tests/support/fakes/process.py`. Changes: `src/devops_cli/commands/k8s/stack_lifecycle.py`, `src/devops_cli/k8s/app_render.py`, `src/devops_cli/k8s/template.py`, `src/devops_cli/lang/en/errors.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_agents_manifests.py`, `tests/support/k8s_tree.py`, `tests/support/k8s_commands.py`, `tests/gate/k8s_checks/deploy_stack.py`, and the tests that start deploy-stack or teardown-stack on a tree with no fake of `kubectl kustomize`.
Adds: `APPLICATIONS_BY_STACK`, `application_not_found`, `path_source_folder`

- [x] 1.1 Write the failing tests in `tests/commands/k8s/test_k8s.py`. `test_deploy_stack_dry_run_lists_the_objects_of_the_build_of_each_path_source` writes a tree under `tmp_path` with the Application `loki` and the fixture Application `logging`, whose path source `env/logging` takes the local component `env/components/perimeter`; the process fake gives two NetworkPolicies for `kubectl kustomize <tmp>/env/logging`. The dry run of `--stack logging` gives them in `details.path_sources` and starts `kubectl kustomize` only as a local read. `test_deploy_stack_applies_the_build_of_each_path_source_and_teardown_deletes_it` runs the deploy and the teardown on a cluster without Argo CD: `kubectl apply -f -` and `kubectl delete -f - --ignore-not-found` get the build as input, before the helm command of `loki`. `test_deploy_stack_stops_before_the_charts_when_the_cluster_refuses_a_build` lets kubectl refuse the build: the command exits 1 with the reason and starts no helm upgrade. `test_deploy_stack_dry_run_fetches_no_path_source_of_another_repository` gives the path source `https://example.com/infra.git` at `v1.0.0`: the objects are `null` and `details.source_fetches` lists the fetch. `test_deploy_stack_stops_on_an_application_that_the_tree_does_not_hold` deletes the Application `logging`: the command exits 1 and names it
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py` fails on the base
- [x] 1.2 Give `build_manifest_path` the keyword `local_read`, and add `path_source_folder` to `devops_cli.k8s.app_render`, which `render_path_source` uses. Add `APPLICATIONS_BY_STACK` (`infra`: `argocd`, `otel`; `logging`: `logging`; `devops`: `agents`; `gitea`: `gitea-manifests`) and remove the rows that its builds replace from `MANIFESTS_BY_STACK`, with a comment on each row that stays. Build the path sources in `_path_builds`, after `_collect_deploy_targets` and `_collect_teardown_targets`, with the `SourceTrees` of the command, apply each build with `kubectl apply -f -` after the manifest paths and stop with kubectl's reason when it refuses one, delete it with `kubectl delete -f - --ignore-not-found` before the manifest paths, and list the builds in `details.path_sources` and `details.path_source_deletes`. Add `ERRORS.k8s.application_not_found`. Delete `test_manifests_by_stack_includes_agents_manifests`, which asserts a value of the table. Give the folders of the table to `deploy_stack_manifests` of `tests/support/k8s_tree.py` and to the ServiceMonitor check of `tests/gate/k8s_checks/deploy_stack.py`, and the process fake or the Applications of the table to the tests that start deploy-stack or teardown-stack
  - Verification: `$ uv run devops ci test tests/commands/k8s tests/commands/test_environment_root_commands.py tests/k8s/test_app_render.py tests/k8s/test_image_pins.py tests/ai/benchmark/test_k8s_llm_gateway.py tests/ai/test_llm_pool_metrics.py tests/commands/test_global_dry_run.py tests/commands/test_k8s_manifest_dry_run.py` passes
- [x] 1.3 Compare the objects of each stack with the base: for each of the 6 stacks, the objects of `details.manifests` and `details.path_sources` of `uv run devops k8s deploy-stack --stack <stack> --no-push-secrets --dry-run` equal the objects of `details.manifests` on the base
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 2. The stack dry runs build each folder with no route to a host that is not a loopback address

Kind: behavior. Reads: `src/devops_cli/k8s/template.py`, `src/devops_cli/core/process.py`, `ProxyFromEnvironment` of Go `net/http` and `golang.org/x/net/http/httpproxy`, `GIT_ALLOW_PROTOCOL` of git(1), the file loader and the git runner of `sigs.k8s.io/kustomize/api`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/core/process.py`, `src/devops_cli/k8s/template.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `tests/core/test_subprocess_env_boundary.py`, `tests/commands/k8s/test_k8s.py`.
Adds: `CONST_GIT_LOCAL_ONLY_ENV`, `CONST_K8S_OFFLINE_PROXY_URL`, `CONST_K8S_KUSTOMIZE_OFFLINE_ENV`, `CONST_KUBECTL_ERROR_PREFIX`

- [x] 2.1 Write the failing tests. `tests/core/test_subprocess_env_boundary.py`: `GIT_ALLOW_PROTOCOL=file` and `GIT_SSH_COMMAND=false` reach the child, and another value or a lower-case key is refused. `test_only_the_dry_runs_build_a_path_source_with_no_route_to_the_network`: with the process fake, the dry runs of deploy-stack and teardown-stack give `kubectl kustomize` the proxy and git keys of design decision 9, and the real runs give no environment. `test_dry_runs_list_a_build_that_fails_and_go_on`: a build that fails with a warning before an error of kubectl over several lines gives `null` objects and the error as one line in `details.kustomize_fetches`, and both dry runs exit 0. `test_the_dry_run_build_of_a_remote_target_fails_at_once_and_is_listed` (`@pytest.mark.live("kubectl")`, a bound of 30 seconds, `_OFFLINE_BUILD_BOUND_SECONDS`): the real `kubectl kustomize` of each form of a remote target at `192.0.2.1`, the `path` of an entry of `patches` included, and of an ssh base at `127.0.0.1` fails with a proxy or transport error, and the dry run lists it. `test_the_dry_run_build_loads_a_file_of_a_loopback_address` (live): Go sends a request to a loopback address with no proxy, so the dry run downloads a file of a server of the test at `127.0.0.1` and lists its object. `test_deploy_stack_dry_run_lists_the_objects_of_the_build_of_each_path_source` also asserts an empty `details.kustomize_fetches`
  - Verification: `$ uv run devops ci test tests/core/test_subprocess_env_boundary.py tests/commands/k8s/test_k8s.py` fails before 2.2: the guard refuses `GIT_ALLOW_PROTOCOL`, and the live builds of a PatchTransformer and of an env file time out
- [x] 2.2 Add the constants. `build_subprocess_env` accepts the two keys of `CONST_GIT_LOCAL_ONLY_ENV` with their values. `build_manifest_path` gets the keyword `offline`, which gives `kubectl kustomize` the environment `CONST_K8S_KUSTOMIZE_OFFLINE_ENV`. In a dry run, `_path_build` sets it, and a failed build gives the error of kubectl as one line, from its prefix `error: ` to its end, which the dry runs list in `details.kustomize_fetches`
  - Verification: `$ uv run devops ci test tests/core/test_subprocess_env_boundary.py tests/commands/k8s/test_k8s.py` passes

## 3. Test the teardown of the builds

Kind: other. Reads: `openspec/specs/k8s-helm-deploy/spec.md`. Changes: `tests/commands/k8s/test_k8s.py`.

- [x] 3.1 `test_teardown_dry_run_lists_the_builds_in_the_order_of_the_deletes` gives the Application `logging` two path sources and compares the order of `details.path_sources` and `details.path_source_deletes`. `test_teardown_stack_stops_before_the_cluster_when_a_build_fails` lets `kubectl kustomize` fail, or deletes the Application: the teardown exits 1 with the reason and starts no `kubectl delete` and no `helm`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py` passes on the code of task 1

## 4. State which objects deploy-stack applies before the charts

Kind: other. Reads: `k8s/README.md`, `src/devops_cli/lang/en/help.py`. Changes: `k8s/README.md`, `ARCHITECTURE.md`, `src/devops_cli/lang/en/help.py`, `docs/commands/k8s.md`, `docs/MCP_TOOLS.md`, the MCP tool listing snapshot.

- [x] 4.1 In `k8s/README.md`, state that deploy-stack builds the path sources of the Applications of `APPLICATIONS_BY_STACK`, applies each build before the charts and lists its objects in the dry run, that a row of `MANIFESTS_BY_STACK` stays only where the build of its Application holds more objects, and that the dry run builds each folder with no route to a host that is not a loopback address, but downloads an http or https URL of a loopback address. In `ARCHITECTURE.md`, state the git keys that the guard of `build_subprocess_env` accepts with one value
  - Verification: `$ uv run devops ci docs` passes
- [x] 4.2 The help of `--dry-run` of deploy-stack says that only local reads of the checkout run, with one exception: `kubectl kustomize` builds its folders with no route to a remote host, but downloads an http or https URL of a loopback address. The generated documents and the MCP tool listing snapshot follow it
  - Verification: `$ uv run devops docs generate --check` passes

## 5. Build no path out of the repository of the source

Kind: behavior. Reads: `src/devops_cli/k8s/argocd_gate.py`. Changes: `src/devops_cli/k8s/app_render.py`, `src/devops_cli/lang/en/errors.py`, `tests/k8s/test_app_render.py`, `tests/commands/k8s/test_k8s.py`.
Adds: `path_source_leaves_repository`

- [x] 5.1 Write the failing tests. `test_a_path_out_of_the_folder_of_its_repository_is_not_built` of `tests/k8s/test_app_render.py` gives the Application `web` the path `../outside`: `write_path_renders` raises `ApplicationSourceError` that names the path, and builds no folder outside. `test_deploy_stack_stops_on_a_path_source_that_leaves_the_repository`: the dry runs of deploy-stack and teardown-stack exit 1, name `../outside` and start no `kubectl kustomize`
  - Verification: `$ uv run devops ci test tests/k8s/test_app_render.py tests/commands/k8s/test_k8s.py` fails on the code of task 2
- [x] 5.2 `path_source_folder` raises `ApplicationSourceError` with `ERRORS.k8s.path_source_leaves_repository` when the folder is not in the folder of its repository, as `argocd_gate` refuses it
  - Verification: `$ uv run devops ci test tests/k8s/test_app_render.py tests/k8s/test_image_pins.py tests/commands/k8s/test_k8s.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
