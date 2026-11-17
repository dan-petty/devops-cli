# Proposal: #6119

## Why
The owner rule of #6060: no test asserts a value of a manifest or a config file, and a test checks the source code of the project. #6082 takes the config-read allow list of the test guard (`tests/gate/tree_checks/config_reads.toml`) to zero, one area per pull request. This change is the first area: the Kubernetes manifests and chart values. The allow list held 141 tests of this area in 23 modules. Closes #6119, part of #6082.

## What Changes
- Delete each test of the area that asserts a value of a manifest, a chart values file or a config file. The owner decision of 2026-11-17 ("Delete them all now") covers the tests of security and privacy controls too. Delete the helpers, the fixtures and the test data that only those tests used.
- Replace each test of source code that read a committed manifest as its input with a test on a fixture that holds the shape, not the live values: the CronJob templates of the roadmap Jobs (`tests/support/job_templates.py`), the Argo CD Applications of a tree, the Ollama profiles, an RBAC binding and a settings mapping.
- The ConfigMap render of `devops k8s deploy-stack` refuses a template key that no setting declares, and names it. A test of the committed template did this check before; the deploy now does it at run time.
- The guard counts a call of a reader of `tests.support.k8s_tree`, and judges a path whole, so `REPO_ROOT / "k8s" / "README.md"` is a document and not a read of `k8s/`. The readers with no user left go from `tests/support/k8s_tree.py`.
- Each spec scenario whose test goes names a validator command or a live check. A requirement whose scenarios described the deleted test goes, and a requirement with a new title holds its rule.
- #6120 (#6118) gave a command proof to the scenarios of the same capabilities first. This change keeps each requirement that #6120 changed or removed, and changes only the scenarios that still name a deleted test.
- The documents that named a deleted test say what checks the rule now.

## Capabilities
- `roadmap-service-deployment`: the render refuses an unknown key (added); two scenarios name a live check (modified).
- `loki-release-pin`: one requirement goes and one with a new title holds its rule.
- `service-account-tokens`, `stack-credential-sync`: the requirement that described a check of the deleted test goes.
- `crawl4ai-service`, `searxng-service`: the scenario of the file lists names the `k8s` row and a dry run (modified).
- `otlp-export`, `roadmap-implement-runner`, `ai-gateway-routing`, `ai-chat-reply-stream`, `roadmap-stage/fix-plan`, `ollama-release-pin`, `ollama-image-pin`, `traefik-release-pin`, `k8s-helm-deploy`, `argocd-github-deployments`, `mattermost-operator-security-context`, `mattermost-app-security-context`, `trivy-config-alerts`, `mcp-server-network-policies`, `mcp-server-token`, `llm-valkey`, `renovate-service`: modified (the scenarios name a validator command or a live check).
- `gitea-forge`, `cluster-image-registry`, `k8s-network-policies`, `grafana-image-renderer`, `gitops-host-overrides`, `llm-gateway-database`, `qdrant-read-only-key`, `local-path-volume-placement`: no delta. #6120 already gives each changed scenario a command proof.

## Impact
- `config_reads.toml` falls from 554 tests in 89 modules to 411 tests in 65 modules.
- Code: `src/devops_cli/k8s/configmap.py` (the render calls `unknown_setting_keys`).
- Tests: 11 modules and one test data file go; 15 modules change; 1 test module and 1 support module are new.
- Documents: `k8s/README.md`, `docs/CLUSTER.md`, `docs/TESTING.md`, `SECURITY.md` and ADR 0027.

## Feasibility
- `uv run devops ci --check --only test-tree,k8s` passes after the change, and the touched test folders pass.
- The committed `k8s/devops/configmap.example.yaml` renders with the new refusal, so a deploy of the current tree is not stopped.
- `build_job` and `ClusterJobs` read the CronJob from the cluster at run time, so a built CronJob in the shape of the template is the right input.

## Existing Tool Considered
- kube-linter (`devops k8s lint`, in CI through #6068), the `kubectl kustomize` renders of the `k8s` row, `trivy config` and kubeconform check the form of the manifests. The live checks `devops k8s searxng-check`, `devops k8s crawl4ai-check`, `devops k8s doctor --stack gitea` and `devops k8s rbac-audit` check the running services. No new tool is built. The change deletes about 5,000 lines of tests.
