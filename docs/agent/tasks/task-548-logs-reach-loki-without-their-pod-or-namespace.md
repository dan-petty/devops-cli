# Task: Pod logs reach loki once and labelled, without duplicate scraping (#548)

**Issue**: [#548](https://github.com/dan-petty/devops-cli/issues/548)
**Status**: Done
**Milestone**: v0.2.26
**Priority**: priority/p1-high
**Scope**: type/fix, scope/k8s, priority/p1-high

## Description
Establishes Grafana Alloy in the `infra` stack as the sole container log collector and shipper to Loki, completely eliminating Fluent Bit from the Kubernetes cluster manifests, Helm stack lifecycle, and test suites.

Removes duplicate log scraping across cluster workloads (`default`, `llm`, `sandbox`), eliminates unlabelled pod log streams caused by Fluent Bit Kubernetes API connection failures, deletes the unauthenticated `fluent-bit-ingress`, and removes unused API server egress rules from `k8s/logging/networkpolicy.yaml`. Drops the `logging` namespace Pod Security Standards enforcement level from `privileged` to `baseline`.

## Acceptance Criteria
- [x] No Fluent Bit remains in code, manifests, or tests (`git grep -n -i fluent -- src k8s tests` returns 0 lines).
- [x] Test `test_logging_stack_definitions_and_single_shipper` in `tests/test_k8s_logging_stack.py` verifies single-shipper structural tuple equality: release names `("loki",)`, Helm repo names `("grafana",)`, `podLogsViaLoki.enabled is True`, and `localLoki` destination `http://loki.logging.svc.cluster.local:3100/loki/api/v1/push`.
- [x] Test `test_monitoring_network_policy_alloy_egress_rules` in `tests/test_k8s_logging_stack.py` verifies egress rules in `k8s/monitoring/networkpolicy.yaml` for TCP 6443 (Alloy API discovery with `0.0.0.0/0` except `169.254.169.254/32`) and TCP 3100 (Loki push to `logging` namespace), matching content resiliently against future rule additions. Verified by manual mutation testing.
- [x] Test `test_logging_stack_security_and_scoping` in `tests/test_k8s_logging_stack.py` asserts bidirectional NetworkPolicy rules: egress restricted to intra-namespace and CoreDNS UDP/TCP 53, and ingress admitting `monitoring` and `otel` on TCP 3100.
- [x] Test `tests/test_k8s.py` verifies `logging` namespace enforces `baseline`, and warns and audits at `baseline`.
- [x] Test call durations in `tests/test_k8s_logging_stack.py` run in under 1 s per test, maintaining cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- [x] `changelog.d/548.md` created under `### Removed` and `### Changed`; `CHANGELOG.md` and `docs/ROADMAP.md` remain untouched.
- Runtime alert when pod logs stop reaching Loki is tracked in follow-up issue #890.
- Pending a person, on cluster after merge:
  ```bash
  helm uninstall fluent-bit -n logging --kube-context <cluster-context> --wait
  kubectl --context <cluster-context> delete ingress fluent-bit-ingress -n logging
  kubectl --context <cluster-context> label --dry-run=server --overwrite ns logging pod-security.kubernetes.io/enforce=baseline
  uv run devops k8s deploy-stack --stack logging --context <cluster-context>
  kubectl --context <cluster-context> get pods -n logging
  kubectl --context <cluster-context> get ns logging --show-labels
  kubectl --context <cluster-context> get networkpolicy logging-default-perimeter -n logging -o jsonpath='{.spec.egress[*].ports[*].port}'
  ```
- Pending a person, 15 minutes after the previous step, with `kubectl --context <cluster-context> port-forward -n logging svc/loki 3100:3100` running in another terminal:
  ```bash
  curl -s -G http://localhost:3100/loki/api/v1/series \
    --data-urlencode 'match[]={job=~".+", source!="kubernetes-events"}' \
    --data-urlencode "start=$(date -d '-10 min' +%s)" \
    | jq '[([.data[] | select(.namespace == null or .container == null)]), ([.data[] | select(.namespace == "llm")] | length > 0)]'
  uv run devops k8s logs '{namespace="llm", container="litellm"}' --loki-url http://localhost:3100 --since 10m --limit 5 --format json
  ```

## Deliverables
- [x] `k8s/logging/fluent-bit-values.yaml`: Deleted obsolete Fluent Bit Helm values file.
- [x] `k8s/ingress/ingress-routes.yaml`: Removed unauthenticated `fluent-bit-ingress` Ingress route.
- [x] `k8s/logging/networkpolicy.yaml`: Removed API server egress rule, updated comments, restricted egress to intra-namespace and CoreDNS.
- [x] `k8s/namespaces.yaml`: Changed `logging` namespace Pod Security Standards enforcement level from `privileged` to `baseline`.
- [x] `k8s/README.md`: Added `logging` row to stack overview table and updated `all` stack description.
- [x] `src/devops_cli/commands/k8s/stack_lifecycle.py`: Removed `fluent` Helm repo and `fluent-bit` Helm release definition.
- [x] `src/devops_cli/config/constants.py`: Removed `fluent-bit` from `CONST_HELM_DAEMONSET_RELEASES`.
- [x] `src/devops_cli/security/kubeconform.py`: Cleaned up docstring references to Fluent Bit.
- [x] `src/devops_cli/ai/knowledge_base/devops_cli/tasks/k8s_stack_deployment.md`: Removed Fluent Bit from stack descriptions and architecture diagram.
- [x] `tests/test_k8s_manifest_validation.py`: Removed Fluent Bit values validation and docstrings.
- [x] `tests/test_k8s.py`: Updated logging namespace Pod Security assertions and removed Fluent Bit values checks.
- [x] `tests/test_k8s_logging_stack.py`: Added single-shipper assertions and Alloy egress tests, updated NetworkPolicy security test.
- [x] `changelog.d/548.md`: Documented removals, changes, and manual cleanup commands.
