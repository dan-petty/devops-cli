# Tasks

## 1. Gitea's chart values, perimeter, namespace and git host

- [x] 1.1 Write the failing tests of the values, the namespace and the git host in `tests/test_k8s_gitea.py`, the perimeter tests in `tests/test_k8s_network_policies.py` (`gitea` in `TARGET_NAMESPACES`, `test_gitea_perimeter_admits_only_its_http_port_from_traefik_argocd_and_its_namespace`) and the update-checker test in `tests/test_third_party_telemetry.py`, and see them fail with `uv run devops ci test tests/test_k8s_gitea.py tests/test_k8s_network_policies.py tests/test_third_party_telemetry.py`
- [x] 1.2 Add `k8s/gitea/values.yaml`, `k8s/gitea/networkpolicy.yaml` and `k8s/gitea/kustomization.yaml`, namespace `gitea` in `k8s/namespaces.yaml` and Ingress `gitea/gitea-ingress` in `k8s/ingress/ingress-routes.yaml`; check the render with `helm template gitea gitea-charts/gitea --version 12.7.0 --namespace gitea -f k8s/gitea/values.yaml`, and verify with `uv run devops ci test tests/test_k8s_gitea.py tests/test_k8s_network_policies.py tests/test_third_party_telemetry.py tests/test_k8s.py`

## 2. Argo CD Applications and the deploy-stack stack

- [x] 2.1 Write the failing tests of the Applications, the projects and the stack in `tests/test_k8s_gitea.py`, and update the resolution of `all` in `tests/test_k8s_devops_stack.py`; see them fail with `uv run devops ci test tests/test_k8s_gitea.py tests/test_k8s_devops_stack.py`
- [x] 2.2 Add `k8s/argocd/apps/gitea.yaml` and `k8s/argocd/apps/gitea-manifests.yaml`, admit the chart repository, namespace `gitea` and the orphan Secret `gitea-admin` in `k8s/argocd/apps/projects.yaml`, and add stack `gitea` to `VALID_STACKS`, `_resolve_stacks`, `_HELM_REPOS_BY_STACK`, `_HELM_RELEASES_BY_STACK`, `_MANIFESTS_BY_STACK` and `CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS_BY_STACK`; verify with `uv run devops ci test tests/test_k8s_gitea.py tests/test_k8s_devops_stack.py tests/test_k8s_argocd_apps.py tests/test_k8s_network_policies.py tests/test_k8s_networking.py`

## 3. The admin Secret from the keyring

- [x] 3.1 Write the failing tests of the row, the option and the dry run in `tests/test_k8s_push_secrets.py`, and count the new key in `tests/test_config_audit_keys.py`; see them fail with `uv run devops ci test tests/test_k8s_push_secrets.py tests/test_config_audit_keys.py`
- [x] 3.2 Add the option `gitea.admin_password` (`src/devops_cli/config/options.py`, `src/devops_cli/config/env.py`, `src/devops_cli/security/secrets.py`), the row `gitea/gitea-admin` in `src/devops_cli/k8s/cluster_secrets.py` and the stack in the `--stack` help of `push-secrets`; verify with `uv run devops ci test tests/test_k8s_push_secrets.py tests/test_config_audit_keys.py tests/test_secret_resolution.py tests/test_config_cmd.py`

## 4. Documentation

- [x] 4.1 Add the Gitea section to `k8s/README.md`, and update its stack table, its Cluster Secrets table, the Homelab Values table, the Application counts, the tunnel diagram, the directory tree and the Internal Image Registry section; update the stack lists in `src/devops_cli/ai/knowledge_base/devops_cli/tasks/k8s_stack_deployment.md` and `docs/DEVCONTAINER_USAGE.md`; verify with `uv run devops docs generate --sync-readme`, `uv run devops docs check` and `uv run devops ci test tests/test_k8s_push_secrets.py -k readme`

## Workflow follow-up

- #1082 points Argo CD at Gitea for git and the pull-request images at Gitea's container registry, and opens Argo CD's egress to Gitea. It chooses the push and pull path of the images: a node's container runtime does not resolve the in-cluster address, and Cloudflare refuses a request body over 100 MB through the tunnel.
- #1090 adds the Gitea remote to each repository under `repos/` and the setting `gitea.url` (`https://git.<domain>`).
- #2144: a scheduled backup of Gitea's data off its node, and a tested restore.
- Pending a person: store the Gitea admin password at a hidden prompt with `uv run devops config set gitea.admin_password`.
- Pending a person: after the merge, run `uv run devops k8s deploy-stack --stack gitea --context <context>`. It pushes Secret `gitea/gitea-admin` and sets the git host on Application `ingress`. Then `kubectl -n argocd get application gitea -o jsonpath='{.status.sync.status} {.status.health.status}{"\n"}'` prints `Synced Healthy`.
- Pending a person: set the reclaim policy of the bound volume to `Retain` with `kubectl patch pv "$(kubectl -n gitea get pvc gitea-shared-storage -o jsonpath='{.spec.volumeName}')" -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'`.
- Pending a person: in Cloudflare, nothing new when the wildcard route and the wildcard Access application with the `homelab-public-ip-bypass` policy are in place. Check with `devops cloudflare tunnel routes` and `devops cloudflare access status --json`, then `devops cloudflare access policies <app-id>`.
- Pending a person: from the devcontainer, `curl -s -o /dev/null -w '%{http_code}\n' https://git.<domain>/api/v1/repos/search` prints `401` or `403`, and `curl -s -u gitea_admin:<password> https://git.<domain>/api/v1/version` prints version `1.27.3`.
- Pending a person: create a test repository in the UI, check that `curl -s -u gitea_admin:<password> https://git.<domain>/api/v1/repos/gitea_admin/<test-repo> | jq -r .clone_url` starts with `https://git.<domain>/` and that the page offers no SSH clone URL, then delete the repository.
- Pending a person: `kubectl -n gitea exec deploy/gitea -- ls /data/gitea.db-wal` succeeds after the first sign-in, `kubectl -n gitea exec deploy/gitea -- curl -s -m 5 -o /dev/null https://github.com` fails, and `kubectl label --dry-run=server --overwrite ns gitea pod-security.kubernetes.io/enforce=restricted` prints no warning.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
