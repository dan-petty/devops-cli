# Tasks

## 1. The environment tree (behavior)

- [x] 1.1 Write failing tests: the option, the profile of the current repository, one infra repo, two infra repos, no source, the product base, and the declaration of this repository
  - Verification: `$ uv run devops ci test tests/k8s/test_environment.py`
- [x] 1.2 Add `devops_cli.k8s.environment` (`EnvironmentTree`, `resolve_environment`, `resolve_product_root`, `tree_at`), the two error messages, and `.devops/project.toml` with `[kubernetes] dir = "k8s"`
  - Verification: `$ uv run devops ci test tests/k8s/test_environment.py`

## 2. The commands read the tree (behavior)

- [x] 2.1 Write failing command tests: a copy of the tree gives the same `deploy-stack --dry-run` and `dashboards lint`, a profile of another repository, no tree, `gateway render`, `ollama prune`, `bootstrap-gitops`, `gitops sync`, `bootstrap-mattermost`, `cloudflare access sync` and `doctor --stack gitea`
  - Verification: `$ uv run devops ci test tests/commands/test_environment_root_commands.py`
- [x] 2.2 Make the stack tables relative to the tree, split the product paths into `PRODUCT_MANIFESTS_BY_STACK`, `PRODUCT_POST_HELM_BY_STACK` and the `product_values` of a release, add `--product-dir`, and read the ConfigMap template from the product base
  - Verification: `$ uv run devops ci test tests/commands/k8s tests/k8s/test_k8s_configmap.py tests/k8s/test_k8s_configmap_keys.py`
- [x] 2.3 Read the tree in `bootstrap`, `image-pins`, `lint`, `check-deprecated`, `ollama prune`, `devops grafana dashboards`, `devops ai gateway render` and `devops argo`, and confine `--product-dir` for the MCP server
  - Verification: `$ uv run devops ci test tests/commands/test_environment_root_commands.py tests/ai/mcp/test_path_confinement.py tests/ai/mcp/test_mcp_tool_listing.py`
- [x] 2.4 Add the settings `argocd.root_applications`, `gitea.applications`, `mattermost.team` and the three `cloudflare.access.*_name` settings, and delete the constants that they replace
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py tests/k8s/test_gitea_doctor.py tests/cloudflare tests/commands/test_cloudflare_commands.py tests/commands/test_cloudflare_dry_run.py tests/security/test_config_declarations.py tests/k8s/test_cluster_secret_plan.py`

## 3. Sources of another repository (behavior)

- [x] 3.1 Write failing tests: the product base of another repository and a second ref, a URL that is not https, a dry run, a kustomization folder, and the gate with another repository
  - Verification: `$ uv run devops ci test tests/k8s/test_image_pins.py tests/k8s/test_k8s_argocd_gate.py`
- [x] 3.2 Add `devops_cli.k8s.app_sources` and `ApplicationSourceError`, use it in `image_pins.py` and `argocd_gate.py`, and add `collect_kustomization_pins`
  - Verification: `$ uv run devops ci test tests/k8s/test_image_pins.py tests/k8s/test_k8s_argocd_gate.py`

## 4. Test readers of the tree (refactor)

- [x] 4.1 Make `tests/support/k8s_tree.py` read a value file of any ref and give `TREE`, and move each test and gate check that read a deleted constant to `TREE` or to the product tables
  - Verification: `$ uv run devops ci test tests/invariants tests/gate tests/ai/benchmark/test_k8s_llm_gateway.py tests/ai/test_ai_gateway_render.py tests/k8s/test_gpu_thresholds.py tests/k8s/test_k8s_ollama_prune.py`
- [x] 4.2 Confirm that no environment constant of the issue is in `src/`
  - Verification: `$ ! git grep -n -w -e DEFAULT_K8S_DIR -e CONST_K8S_ARGOCD_APPLICATION_DIRS -e CONST_K8S_ARGOCD_PAUSE_PARENTS -e CONST_K8S_GITEA_APPLICATIONS -e CONST_K8S_OLLAMA_PROFILES_PATH -e DEFAULT_GRAFANA_DASHBOARDS_DIR -e DEFAULT_GRAFANA_DASHBOARDS_DIRS -e DEFAULT_LLM_GATEWAY_CONFIG_PATH -e DEFAULT_LLM_PROFILES_PATH -e CONST_CLOUDFLARE_BYPASS_POLICY_NAME -e CONST_CLOUDFLARE_ALLOW_POLICY_NAME -- src`

## 5. Workflows (workflow)

- [x] 5.1 Delete the dead filter `k8s/startpage/**` of the job `design-tokens` and of `DESIGN_FILTER`, and run `image-pins.yml` on a change to its new modules and to `.devops/project.toml`
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`

## 6. Documents

- [x] 6.1 Regenerate the reference documents, and describe the environment tree in `k8s/README.md`, `CONTEXT.md`, `docs/SDLC.md` and `config.example.yaml`
  - Verification: `$ uv run devops docs generate --check`

## Workflow follow-up

- The product-contract tests on a fixture tree are #5298.
- The fetch of a private Application repository is #5294.
- The environment tests move to homelab CI in #5296.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
