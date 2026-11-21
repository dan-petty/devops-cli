# Tasks

## 1. deploy-stack applies the builds of the path sources of the Applications

Kind: behavior. Reads: `src/devops_cli/k8s/app_render.py`, `src/devops_cli/k8s/app_sources.py`, `src/devops_cli/k8s/argocd_gate.py`, `src/devops_cli/k8s/template.py`, `tests/support/fakes/process.py`. Changes: `src/devops_cli/commands/k8s/stack_lifecycle.py`, `src/devops_cli/k8s/app_render.py`, `src/devops_cli/k8s/template.py`, `src/devops_cli/lang/en/errors.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_agents_manifests.py`, `tests/support/k8s_tree.py`, `tests/gate/k8s_checks/deploy_stack.py`, and the tests that start deploy-stack or teardown-stack on a tree with no fake of `kubectl kustomize`.
Adds: `APPLICATIONS_BY_STACK`, `application_not_found`

- [ ] 1.1 Write the failing tests in `tests/commands/k8s/test_k8s.py`. `test_deploy_stack_dry_run_lists_the_objects_of_the_build_of_each_path_source` writes a tree under `tmp_path` with the Application `loki` and the fixture Application `logging`, whose path source `env/logging` takes the local component `env/components/perimeter`; the process fake gives two NetworkPolicies for `kubectl kustomize <tmp>/env/logging`. The dry run of `--stack logging` gives them in `details.path_sources` and starts `kubectl kustomize` only as a local read. `test_deploy_stack_applies_the_build_of_each_path_source_and_teardown_deletes_it` runs the deploy and the teardown on a cluster without Argo CD: `kubectl apply -f -` and `kubectl delete -f - --ignore-not-found` get the build as input, before the helm command of `loki`. `test_deploy_stack_dry_run_fetches_no_path_source_of_another_repository` gives the path source `https://example.com/infra.git` at `v1.0.0`: the objects are `null` and `details.source_fetches` lists the fetch. `test_deploy_stack_stops_on_an_application_that_the_tree_does_not_hold` deletes the Application `logging`: the command exits 1 and names it
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py` fails on the base
- [ ] 1.2 Give `build_manifest_path` and `render_path_source` the keyword `local_read`. Add `APPLICATIONS_BY_STACK` (`infra`: `argocd`, `otel`; `logging`: `logging`; `devops`: `agents`; `gitea`: `gitea-manifests`) and remove the rows that its builds replace from `MANIFESTS_BY_STACK`, with a comment on each row that stays. Build the path sources in `_collect_deploy_targets` and `_collect_teardown_targets` with the `SourceTrees` of the command, apply each build with `kubectl apply -f -` after the manifest paths, delete it with `kubectl delete -f - --ignore-not-found` before the manifest paths, and list the builds in `details.path_sources` and `details.path_source_deletes`. Add `ERRORS.k8s.application_not_found`. Delete `test_manifests_by_stack_includes_agents_manifests`, which asserts a value of the table. Give the folders of the table to `deploy_stack_manifests` of `tests/support/k8s_tree.py` and to the ServiceMonitor check of `tests/gate/k8s_checks/deploy_stack.py`, and the process fake or the Applications of the table to the tests that start deploy-stack or teardown-stack
  - Verification: `$ uv run devops ci test tests/commands/k8s tests/commands/test_environment_root_commands.py tests/k8s/test_app_render.py tests/k8s/test_image_pins.py tests/ai/benchmark/test_k8s_llm_gateway.py tests/ai/test_llm_pool_metrics.py tests/commands/test_global_dry_run.py` passes
- [ ] 1.3 Compare the objects of each stack with the base: for each of the 6 stacks, the objects of `details.manifests` and `details.path_sources` of `uv run devops k8s deploy-stack --stack <stack> --no-push-secrets --dry-run` equal the objects of `details.manifests` on the base
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 2. State which objects deploy-stack applies before the charts

Kind: other. Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [ ] 2.1 In `k8s/README.md`, state that deploy-stack builds the path sources of the Applications of `APPLICATIONS_BY_STACK`, applies each build before the charts and lists its objects in the dry run, and that a row of `MANIFESTS_BY_STACK` stays only where the build of its Application holds more objects
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
