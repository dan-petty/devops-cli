# Task: Argo CD namespace perimeter & ApplicationSet controller replicas

**Issue**: [#1673](https://github.com/dan-petty/devops-cli/issues/1673)
**Scope**: Deploy the `argocd-default-perimeter` NetworkPolicy through Argo CD and configure ApplicationSet controller replicas to 0.
**Feasibility**: Verified upstream argo-cd Helm chart parameters (where `applicationSet.replicas: 0` disables controller deployment pods while retaining RBAC and Service resources) and verified Argo CD multi-source topology deploying `k8s/argocd/kustomization.yaml` containing the `argocd-default-perimeter` NetworkPolicy.

## Deliverables

- [x] Configured `applicationSet.replicas: 0` and removed obsolete `applicationSet.enabled` key in `k8s/argocd/values.yaml`.
- [x] Added `k8s/argocd` path as a source in `k8s/argocd/apps/argocd.yaml` to deploy `argocd-default-perimeter` through Argo CD.
- [x] Updated `tests/test_k8s_network_policies.py` so a policy counts as deployed only when rendered by both native deploy-stack and an Argo CD Application (or carrying an owned exemption).
- [x] Updated `tests/test_k8s_argocd_apps.py` to assert exactly one Application renders `argocd-default-perimeter` and that `applicationSet.replicas == 0` without `enabled`.
- [x] Authored changelog fragment `changelog.d/1673.md` under `### Security`.
