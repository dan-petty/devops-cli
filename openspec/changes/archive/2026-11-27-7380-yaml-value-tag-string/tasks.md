# Tasks

## 1. Read a plain equals of a render as a string

Kind: behavior. Reads: `src/devops_cli/core/serialization.py`, `src/devops_cli/k8s/catalog.py`, `src/devops_cli/k8s/argocd_gate.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`. Changes: `src/devops_cli/core/serialization.py`, `src/devops_cli/k8s/argocd_gate.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `tests/core/test_serialization.py`, `tests/k8s/test_k8s_catalog.py`, `tests/k8s/test_k8s_argocd_gate.py`, `tests/commands/k8s/test_k8s.py`.

- [x] 1.1 Add `test_shared_safe_loader_reads_a_plain_equals_as_a_string` in `tests/core/test_serialization.py`, `test_catalog_reads_a_chart_render_that_holds_a_plain_equals` in `tests/k8s/test_k8s_catalog.py`, `test_a_path_build_that_holds_a_plain_equals_passes` in `tests/k8s/test_k8s_argocd_gate.py` and `test_deploy_stack_dry_run_lists_a_build_that_holds_a_plain_equals` in `tests/commands/k8s/test_k8s.py`
  - Verification: `$ uv run devops ci test tests/core/test_serialization.py tests/k8s/test_k8s_catalog.py tests/k8s/test_k8s_argocd_gate.py tests/commands/k8s/test_k8s.py` fails on the base
- [x] 1.2 Register a constructor for `tag:yaml.org,2002:value` on a subclass of the loader of `YAML_SAFE_LOADER`, and load the Kustomize build of the Argo CD gate and of `_PathBuild.objects` with `YAML_SAFE_LOADER`
  - Verification: `$ uv run devops ci test tests/core/test_serialization.py tests/k8s/test_k8s_catalog.py tests/k8s/test_k8s_argocd_gate.py tests/commands/k8s/test_k8s.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
