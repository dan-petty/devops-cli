# Tasks

## 1. Network perimeters (behavior)

- [x] 1.1 Write failing tests: the cert-manager perimeter, the webhook policy, the plugin policy in `cnpg-system`, the monitoring egress to 9402, and the namespace `cert-manager` with Pod Security `restricted`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_network_policies.py tests/invariants/test_k8s_argocd_apps.py`
- [x] 1.2 Add namespace `cert-manager`, `k8s/cert-manager/` and `k8s/cnpg-system/` with their policies and kustomizations, list both in the root kustomization, and add the cert-manager scrape to the monitoring perimeter
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_network_policies.py tests/invariants/test_k8s_argocd_apps.py`

## 2. Applications and install order (behavior)

- [x] 2.1 Write failing tests: every Application source is a repository of its project, deploy-stack installs the plugin after the operator and cert-manager, Argo CD syncs the plugin after cert-manager, cert-manager keeps its CRDs and its lease, and the claim table and the token table name both charts with the role of each pod
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_argocd_apps.py tests/invariants/test_k8s_manifests.py tests/core/test_k8s_local_path_placement.py`
- [x] 2.2 Add Applications `cert-manager` and `plugin-barman-cloud`, the AppProject entries, the values files, the Helm repository `jetstack` and the two releases of stack `infra`
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_argocd_apps.py tests/invariants/test_k8s_manifests.py tests/core/test_k8s_local_path_placement.py`
- [x] 2.3 Run the `k8s` row of `devops ci`
  - Verification: `$ uv run devops ci --check --only k8s`

## 3. Documents

- [x] 3.1 Add the section "CloudNativePG Backup Plugin" to `k8s/README.md`, with the stack rows, the scrape list and the directory tree
  - Verification: `$ uv run devops ci docs`

- Pending a person: after the merge, check that Applications `cert-manager` and `plugin-barman-cloud` are Synced and Healthy and that Certificates `barman-cloud-client` and `barman-cloud-server` in `cnpg-system` are Ready (the pull request comment lists the commands).
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
