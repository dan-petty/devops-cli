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

## 2. The stack dry runs build no folder that reaches a remote target

Kind: behavior. Reads: `src/devops_cli/k8s/app_render.py`, `src/devops_cli/k8s/template.py`, the Kustomization schema and the loader of `sigs.k8s.io/kustomize/api`. Changes: `src/devops_cli/k8s/kustomize_remotes.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `src/devops_cli/lang/en/errors.py`, `tests/k8s/test_kustomize_remotes.py`, `tests/commands/k8s/test_k8s.py`.
Adds: `remote_targets`, `kustomization_not_mapping`

- [x] 2.1 Write the failing tests. `tests/k8s/test_kustomize_remotes.py` writes kustomizations under `tmp_path`: a remote target of a local base, of a local component and of a folder of `bases` counts, each form of a remote entry counts and a local path does not, a file field counts only as an http or https URL, a cycle of local bases ends, and a kustomization that is not a mapping stops the read. `test_dry_runs_build_no_folder_whose_kustomization_reaches_a_remote_base` gives the folder `env/logging` the local base `../bases/loki`, which names a remote base: the dry runs of deploy-stack and teardown-stack start no `kubectl kustomize`, give `null` as the objects and list the remote base in `details.kustomize_fetches`. `test_deploy_stack_dry_run_lists_the_objects_of_the_build_of_each_path_source` also asserts an empty `details.kustomize_fetches`
  - Verification: `$ uv run devops ci test tests/k8s/test_kustomize_remotes.py tests/commands/k8s/test_k8s.py` fails before 2.2
- [x] 2.2 Add `remote_targets` and `ERRORS.k8s.kustomization_not_mapping`. In a dry run, `_path_build` builds no folder that `remote_targets` gives an entry for, and the dry runs list the entries in `details.kustomize_fetches`
  - Verification: `$ uv run devops ci test tests/k8s/test_kustomize_remotes.py tests/commands/k8s/test_k8s.py` passes

## 3. Test the teardown of the builds

Kind: other. Reads: `openspec/specs/k8s-helm-deploy/spec.md`. Changes: `tests/commands/k8s/test_k8s.py`.

- [x] 3.1 `test_teardown_dry_run_lists_the_builds_in_the_order_of_the_deletes` gives the Application `logging` two path sources and compares the order of `details.path_sources` and `details.path_source_deletes`. `test_teardown_stack_stops_before_the_cluster_when_a_build_fails` lets `kubectl kustomize` fail, or deletes the Application: the teardown exits 1 with the reason and starts no `kubectl delete` and no `helm`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py` passes on the code of task 1

## 4. State which objects deploy-stack applies before the charts

Kind: other. Reads: `k8s/README.md`, `src/devops_cli/lang/en/help.py`. Changes: `k8s/README.md`, `src/devops_cli/lang/en/help.py`, `docs/commands/k8s.md`, `docs/MCP_TOOLS.md`, the MCP tool listing snapshot.

- [x] 4.1 In `k8s/README.md`, state that deploy-stack builds the path sources of the Applications of `APPLICATIONS_BY_STACK`, applies each build before the charts and lists its objects in the dry run, that a row of `MANIFESTS_BY_STACK` stays only where the build of its Application holds more objects, and that the dry run does not build a folder that reaches a remote target
  - Verification: `$ uv run devops ci docs` passes
- [x] 4.2 The help of `--dry-run` of deploy-stack says that only local reads of the checkout run, such as `kubectl kustomize`, and the generated documents and the MCP tool listing snapshot follow it
  - Verification: `$ uv run devops docs generate --check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
