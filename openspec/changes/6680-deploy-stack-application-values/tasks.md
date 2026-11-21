# Tasks

## 1. deploy-stack takes the values files of each release from its Application

Kind: behavior. Reads: `src/devops_cli/k8s/app_sources.py`, `src/devops_cli/k8s/environment.py`, `src/devops_cli/k8s/image_pins.py`, `src/devops_cli/commands/k8s/image_pins.py`, `src/devops_cli/main.py`. Changes: `src/devops_cli/k8s/app_sources.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `tests/commands/k8s/test_k8s.py`, `tests/k8s/test_app_sources.py`, `tests/support/k8s_tree.py`, `tests/gate/k8s_checks/deploy_stack.py`, `tests/ai/test_llm_pool_metrics.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/commands/k8s/test_k8s_qdrant_security.py`, `tests/commands/k8s/test_k8s_gpu_placement.py`.
Adds: `ChartSource`, `chart_sources`, `_source_trees`

- [x] 1.1 Write the failing test `test_deploy_stack_gives_a_chart_the_values_files_of_its_application_in_their_order` in `tests/commands/k8s/test_k8s.py`. It writes a tree under `tmp_path` with the fixture Application `loki`: a chart source that pins `1.0.0` and lists `$infra/helm/loki/values.yaml` and then `$values/env/logging/loki-values.yaml`, the source `https://example.com/infra.git` at `v1.0.0` with `ref: infra`, and the source `https://github.com/dan-petty/devops-cli` at `main` with `ref: values`. `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` then gives `--values <fetch>/helm/loki/values.yaml --values <tmp>/env/logging/loki-values.yaml` in that order, and `details.source_fetches` holds the `git init`, the shallow `git fetch` of `https://example.com/infra` at `v1.0.0` and the checkout of `FETCH_HEAD` into `<fetch>`. The base gives only the environment file
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py` fails on the base
- [x] 1.2 Change `test_deploy_stack_gives_a_chart_the_environment_values_then_the_product_values` of `tests/commands/k8s/test_k8s.py` into `test_deploy_stack_gives_the_prometheus_chart_the_values_files_of_its_application`: the Application `prometheus` of the tree lists `$values/env/monitoring/prometheus-values.yaml` and then `$values/env/devops/monitoring/prometheus-rules-values.yaml`, and the command takes no `--product-dir`. Change the tests of `tests/k8s/test_app_sources.py` to test `chart_sources`, with the values files and the refs of each chart source
  - Verification: `$ uv run devops ci test tests/k8s/test_app_sources.py` fails on the base
- [x] 1.3 In `src/devops_cli/k8s/app_sources.py`, replace `chart_versions` with `chart_sources`, which gives a `ChartSource` (the version, the values files in their order, and the sources with a `ref`) for each Application with a chart source that pins a version
  - Verification: `$ uv run devops ci test tests/k8s/test_app_sources.py` passes
- [x] 1.4 In `src/devops_cli/commands/k8s/stack_lifecycle.py`, remove `values` and `product_values` from the rows of `HELM_RELEASES_BY_STACK`, make `StackRelease.values` `NotRequired`, and let `_release_at` resolve each values file of the `ChartSource` of the release with `SourceTrees.value_file`. Give `SourceTrees` the field `dry_run`, with which a fetch only records its commands. `deploy_stack` makes one `SourceTrees` (`_source_trees`: the checkout relative to the current folder when the root is relative, and `dry_run` for its own `--dry-run` or the dry-run state) in a `tempfile.TemporaryDirectory` that it holds for the rest of the command, and lists `trees.planned` in `details.source_fetches`. `_stack_roots` asks for the product base only for product manifests and post-Helm paths. Change `release_values` of `tests/support/k8s_tree.py` to read the Application of the release with a work folder of the caller, and change its readers `tests/gate/k8s_checks/deploy_stack.py`, `tests/ai/test_llm_pool_metrics.py` and `tests/ai/benchmark/test_k8s_llm_gateway.py`. The tests that assert that a dry run, or a refusal before the cluster, starts no process leave out a local read
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py tests/k8s/test_app_sources.py tests/commands/k8s/test_k8s_logging_stack.py tests/commands/test_environment_root_commands.py tests/commands/k8s/test_k8s_qdrant_security.py tests/commands/k8s/test_k8s_context.py tests/commands/k8s/test_k8s_gpu_placement.py tests/ai/test_llm_pool_metrics.py tests/ai/benchmark/test_k8s_llm_gateway.py` passes

## 2. State where the values files of a release come from

Kind: other. Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [ ] 2.1 In `k8s/README.md`, state that a row of `HELM_RELEASES_BY_STACK` gives the name, the chart and the namespace of a release, and that deploy-stack takes its version and its values files from the Application of the same name. Remove the table from the step of a Gitea chart update, because the table holds no version
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
