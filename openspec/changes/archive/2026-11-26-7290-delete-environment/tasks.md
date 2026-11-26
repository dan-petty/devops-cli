# Tasks

## 1. A command refuses a tree that does not hold what it reads (behavior)

- [x] 1.1 Write the failing tests: each command on a tree with no environment, a lint with no object, a render with no image, a deploy and a Mattermost bootstrap with no Secret table.
  - Verification: `$ uv run devops ci test tests/k8s/test_empty_environment_tree.py`
- [x] 1.2 Add `EnvironmentTree.require` and `require_applications`, call them from each command, give kube-linter `--fail-if-no-objects-found`, and refuse renders with no image.
  - Verification: `$ uv run devops ci test tests/k8s/test_empty_environment_tree.py tests/k8s/test_environment.py`
- [x] 1.3 Remove the fixture fallback of the cluster Secret table, and keep the product rows readable with no tree.
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secrets_file.py tests/commands/test_config_commands.py`
- [x] 1.4 Add `--k8s-dir` to `devops k8s bootstrap-mattermost`.
  - Verification: `$ uv run devops ci test tests/commands/test_k8s_bootstrap_mattermost.py`
- [x] 1.5 Make row 13 of `devops repos onboard` check the environment tree and pass it to the deploy.
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py`
- [x] 1.6 Make `deploy-stack` and `teardown-stack` refuse a tree that lacks a path of a selected stack, and name `llm/valkey`, the folder that the environment repository holds.
  - Verification: `$ uv run devops ci test tests/k8s/test_empty_environment_tree.py tests/commands/k8s/test_k8s.py`
- [x] 1.7 Make `argo gitops drift` and `watch --once` refuse a watched path with no manifest and no change.
  - Verification: `$ uv run devops ci test tests/argo/test_argo_gitops.py`
- [x] 1.8 Make `k8s catalog` say when the tree has no SLO folder.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_catalog.py`

## 2. The structure check (behavior)

- [x] 2.1 Add `tests/gate/k8s_checks/product_tree.py` with its case on a fixture git tree.
  - Verification: `$ uv run devops ci --check --only k8s`

## 3. Delete the environment (deletion)

- [x] 3.1 Delete each environment file under `k8s/`, and `[kubernetes]` of `.devops/project.toml`.
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 3.2 Delete the `charts` row, the freeze check, the environment gate modules, tests and fixtures, and keep their product checks.
  - Verification: `$ ! git grep -n -F environment_freeze -- src tests`
- [x] 3.3 Move the command tests to a fixture environment tree.
  - Verification: `$ uv run devops ci test tests/commands/k8s tests/k8s tests/invariants`

## 4. Workflows, rows and configuration (data)

- [x] 4.1 Make the `kube-linter` row, `image-pins.yml`, `third-party-image-scan.yml`, the Design Tokens job, `Makefile`, `.github/renovate.json` and `.trivyignore.yaml` read product files only.
  - Verification: `$ uv run devops ci --check --only kube-linter,actionlint,zizmor`

## 5. Documents

- [x] 5.1 Regenerate the generated documents for the changed help text and messages.
  - Verification: `$ uv run devops ci docs`
- [x] 5.2 Update `k8s/README.md`, the documents of `docs/`, ADR 0035 and the knowledge base pages that name a deleted path.
  - Verification: `$ uv run devops ci docs`
- [x] 5.3 Correct the Purpose of each capability that a delta cannot change: `ai-gateway-routing`, `argo-helm-record-retirement`, `cluster-secret-keys`, `gateway-caller-telemetry`, `gitea-forge`, `gitops-host-overrides`, `k8s-network-policies`, `llm-valkey`, `product-monitoring-content`, `project-brain/shared-cache`, `service-account-tokens` and `service-dashboard-template`.
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- The open changes #4530 and #4576 add requirements to the retired capabilities `homelab-project-destinations` and `monitoring-collectors`. They are work of the environment repository, and their change folders need a new plan or a removal before they archive.
- The backlog items that name a deleted path move to the environment repository or are blocked. This change does not edit them.

- Pending a person: run shared check 7 of `docs/HOMELAB_REPO_SWITCH.md` on the live cluster before the merge.

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
