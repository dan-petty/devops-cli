# Task: Argo CD pre-delete finalizers on child apps

**Issue**: [#1674](https://github.com/dan-petty/devops-cli/issues/1674)
**Scope**: Ignore dynamically injected pre/post-delete finalizers in child Applications to prevent cyclic OutOfSync sync loops in the cluster app-of-apps.
**Feasibility**: Verified against live Argo CD behavior and official documentation for `ignoreDifferences` using `jqPathExpressions` on `Application` resources without name constraint; confirmed jq filter selects PreDelete and PostDelete finalizers while preserving the `resources-finalizer.argocd.argoproj.io`.

## Deliverables

- [x] Added `CONST_K8S_ARGOCD_PRE_POST_DELETE_FINALIZERS_JQ` to `src/devops_cli/config/constants.py` defining the standard jq expression.
- [x] Configured `ignoreDifferences` with `jqPathExpressions` for `group: argoproj.io`, `kind: Application` in `k8s/argocd/bootstrap/cluster.yaml`.
- [x] Added unit tests in `tests/test_k8s_argocd_apps.py` asserting `cluster.yaml` ignores pre/post-delete finalizers and validating the jq expression behavior.
- [x] Authored changelog fragment `changelog.d/1674.md`.
