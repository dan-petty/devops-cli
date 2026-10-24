# Tasks

Selection: the owner decided on 2026-10-24 that the internal registry moves to Gitea's container registry (#1081), so this change delivers the issue's "Remove" branch.

## 1. The in-cluster registry leaves the manifests

- [x] 1.1 Write the failing test `test_no_manifest_runs_an_in_cluster_image_registry` in `tests/test_k8s.py`, and see it fail before the removal with `uv run devops ci test tests/test_k8s.py -k test_no_manifest_runs_an_in_cluster_image_registry`
- [x] 1.2 Delete `k8s/registry/`, remove `registry` from `k8s/kustomization.yaml` and the Namespace `registry` from `k8s/namespaces.yaml`, and remove the egress rule to port 5001 in namespace `registry` from `k8s/monitoring/networkpolicy.yaml`; verify with `uv run devops ci test tests/test_k8s.py tests/test_k8s_network_policies.py tests/test_k8s_cloudflared.py tests/test_k8s_argocd_apps.py`
- [x] 1.3 Delete the tests of the removed registry, the memory assertion in `tests/test_k8s.py` and the registry scrape entries in `tests/test_k8s_monitoring_integration.py`, and keep the recorded report in `tests/test_security_kubelinter.py`; verify with `uv run devops ci test tests/test_k8s.py tests/test_k8s_monitoring_integration.py tests/test_security_kubelinter.py`
- [x] 1.4 Record the decision in `k8s/README.md` (Internal Image Registry), and remove the registry from the scrape list and the directory tree of `k8s/README.md` and from `src/devops_cli/ai/knowledge_base/devops_cli/tasks/k8s_stack_deployment.md`; verify with `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## Workflow follow-up

- Pending a person: after the merge, when Argo CD has pruned Deployment `registry/registry` and Service `registry/registry`, delete PVC `registry-data` and Namespace `registry` with the commands in `k8s/README.md` (Internal Image Registry). Until then, Application `base` is OutOfSync and `ArgoCdApplicationOutOfSync` fires.
- Pending a person: dan-petty/homelab#7 points its node mirrors at Gitea's container registry (#1081) instead of the removed registry.
- Remove `registry` from the destinations of the AppProjects `homelab` and `homelab-system` in `k8s/argocd/apps/projects.yaml` after a person deletes the namespace: #1646 does this, as it lets each AppProject allow only the namespaces that its applications use.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
