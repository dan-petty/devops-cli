# Tasks

## 1. The lint of the environment tree

Kind: behavior. Reads: `src/devops_cli/k8s/app_sources.py`, `src/devops_cli/k8s/argocd_gate.py`. Changes: `src/devops_cli/k8s/app_render.py`, `src/devops_cli/k8s/image_pins.py`, `src/devops_cli/commands/k8s/security_audit.py`, `src/devops_cli/security/kubelinter.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/k8s/test_app_render.py`, `tests/commands/k8s/test_k8s.py`, `tests/config/test_command_builders.py`.

- [x] 1.1 Write failing tests: the builds of the path sources go to one folder named for each Application and source place, with no chart build and no fetched file; `devops k8s lint --k8s-dir <tree>` lints that folder with `--config` at the config of the repository, and without it when the repository has none; `build_kubelinter_cmd` adds `--config`
  - Verification: `$ uv run devops ci test tests/k8s/test_app_render.py tests/commands/k8s/test_k8s.py tests/config/test_command_builders.py`
- [x] 1.2 Add `write_path_renders` and `render_path_source`, use `render_path_source` in `devops k8s image-pins`, and make `devops k8s lint` with no target lint the builds with the config of the repository
  - Verification: `$ uv run devops ci test tests/k8s tests/commands/k8s/test_k8s.py tests/commands/test_k8s_manifest_dry_run.py tests/commands/test_environment_root_commands.py`

## 2. The kube-linter row and CI

Kind: behavior. Changes: `src/devops_cli/commands/ci.py`, `src/devops_cli/roadmap/runner_tools.py`, `tests/commands/test_ci_row_commands.py`, `.github/workflows/ci.yml`, `.github/workflows/image-pins.yml`.

- [x] 2.1 Write a failing test: the row `kube-linter` runs `uv run devops k8s lint` alone, before the row `k8s`
  - Verification: `$ uv run devops ci test tests/commands/test_ci_row_commands.py`
- [x] 2.2 Add the row, install the pinned kube-linter in the Static Analysis job, skip kube-linter in the Security Scan step, and give kube-linter its runner reason
  - Verification: `$ uv run devops ci --check --only kube-linter,actionlint,zizmor`

## 3. The checks and the findings of the manifests

Kind: other. Changes: `.kube-linter.yaml`, `k8s/cloudflared/deployment.yaml`, `k8s/devops/crawl4ai/deployment.yaml`, `k8s/devops/cronjob.yaml`, `k8s/devops/cronjob-runner.yaml`, `k8s/devops/cronjob-stage.yaml`, `k8s/devops/mcp-server/deployment.yaml`, `k8s/devops/renovate/cronjob.yaml`, `k8s/devops/roadmap-service/cronjob-planner-run.yaml`, `k8s/devops/roadmap-service/deployment.yaml`, `k8s/devops/searxng/deployment.yaml`, `k8s/gpu-feature-discovery/daemonset.yaml`, `k8s/llm/gateway/deployment.yaml`, `k8s/llm/portkey/deployment.yaml`, `k8s/llm/profiles/kustomization.yaml`, `k8s/llm/profiles/ollama-profiles.yaml`, `k8s/llm/valkey.yaml`, `k8s/llm/valkey-devops.yaml`, `k8s/llm/valkey-runs.yaml`.

- [x] 3.1 Write `.kube-linter.yaml` with the default checks, the checks of the service patterns and `pvc-prune-protection`
  - Verification: `$ uv run devops k8s lint`
- [x] 3.2 Set the explicit rolling strategy where Kubernetes already used it, and give each other finding the annotation with its reason and issue
  - Verification: `$ uv run devops ci --check --only kube-linter,k8s`

## 4. Documents

Kind: other. Changes: `docs/SERVICE_PATTERNS.md`, `docs/ROUTINE_TASKS.md`, `k8s/README.md`, `src/devops_cli/ai/knowledge_base/it_domains/tools/kubelinter_popeye_pluto.md`, `src/devops_cli/ai/knowledge_base/devops_cli/cli_command_reference.md`, the generated command references.

- [x] 4.1 Name the `kube-linter` row in the service patterns, run `devops k8s lint` with no target in the routine tasks and the knowledge base, record the Ollama exception, and generate the references
  - Verification: `$ uv run devops ci --check --only docs`
