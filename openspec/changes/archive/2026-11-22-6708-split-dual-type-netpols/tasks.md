# Tasks

## 1. The row for policies with both types (behavior)

- [x] 1.1 Write the fixture checks of `dual_type_problems` in `tests/gate/k8s_checks/network_policies.py`: a policy that writes both types, a policy with no types and an egress rule, single-type policies with written and with default types, and the scan of the tree
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.2 Write `dual_type_problems`, which refuses each policy whose types, as the API server sets them, hold `Ingress` and `Egress`
  - Verification: `$ uv run devops ci --check --only k8s`

## 2. Single-type policies (manifests)

- [x] 2.1 Split each policy with both types of namespaces `argocd`, `gitea`, `llm`, `logging`, `mattermost`, `monitoring`, `object-store` and `otel` into `<name>-ingress` and `<name>-egress`, and give the in-namespace egress rule of `gitea-default-perimeter-egress` TCP 3000
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 2.2 Split `argo-workflows-default-perimeter`, `cert-manager-default-perimeter`, `cloudflared-isolation` and `plugin-barman-cloud` in the same way
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 2.3 Split `devops-default-perimeter`, `crawl4ai-perimeter`, `renovate-perimeter` and `searxng-perimeter` in the same way, and use the new names in the comments of `k8s/devops/`
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 2.4 Make the checks of the `k8s` row and the tests that look up a split policy read the new name
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py tests/ai/test_ai_gateway_portkey.py tests/k8s/test_k8s_argo_workflows.py tests/server/routes/test_k8s_roadmap_service.py tests/commands/k8s/test_k8s.py`

## 3. Documents

- [x] 3.1 Add the section `NetworkPolicy` to `k8s/README.md` with the controller behavior and the rule, and use the new names in its sections, its tree and `docs/CLUSTER.md`
  - Verification: `$ uv run devops ci docs`

## Checks after the sync

- Pending a person: after Argo CD syncs `main`, `kubectl get networkpolicy -A -o json | jq -r '.items[] | select((.spec.policyTypes | index("Ingress")) and (.spec.policyTypes | index("Egress"))) | .metadata.namespace + "/" + .metadata.name'` prints no policy.
- Pending a person: after the sync, in each changed namespace a probe pod that the ingress rules do not admit runs `nc -z -w 3 <server pod IP> <limited port>` on the node of the server pod and on a second node, and exits 1; and `uv run devops argo cd apps status <app>` shows each Application of the changed namespaces as Synced and Healthy.
- Pending a person: send the private report of the controller behavior to the private vulnerability reporting of kube-router and to the security contact of k3s.
