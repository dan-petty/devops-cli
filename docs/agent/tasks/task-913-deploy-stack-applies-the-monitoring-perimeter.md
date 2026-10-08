# Task: deploy-stack Applies the Monitoring Namespace Perimeter (#913)

**Issue**: [#913](https://github.com/dan-petty/devops-cli/issues/913)
**Status**: Done
**Milestone**: v0.2.29
**Priority**: priority/p1-high
**Scope**: scope/k8s

## Description
`k8s/monitoring/networkpolicy.yaml` defines `monitoring-default-perimeter`, the default-deny ingress and egress policy for every pod in namespace `monitoring`. Checked at release/v0.2.29 (910b823): a native `devops k8s deploy-stack` applies the root kustomization, `_KUSTOMIZATIONS_BY_STACK` (`monitoring/dashboards` only) and `_MANIFESTS_BY_STACK`, and none of them names the file. `kubectl kustomize k8s` renders only `cloudflared-isolation`. Argo CD's `monitoring` Application syncs `k8s/monitoring`, policy included, since #755, so the gap was on clusters without Argo CD: every pod there could reach Prometheus (no authentication, accepts remote writes), Grafana (anonymous Viewers), Alloy and Pyroscope.

A native `deploy-stack --stack infra` (or `all`) now applies the whole `monitoring` kustomization, which lists `networkpolicy.yaml` and `dashboards`. It runs right after the root kustomization creates the namespace and before any Secret or chart, so it applies exactly what Argo CD's `monitoring` Application syncs. A new guard test covers every NetworkPolicy under `k8s/`.

## Decisions
The issue body's deploy path no longer fit the tree. The amendment of 2026-10-08 and its challenge settled it as follows:

1. **The root kustomization stays as it is (replaces AC1 and key question 1).** #1279 took `monitoring/dashboards` out of the root so that Argo CD's `base` and `monitoring` Applications never own the same objects (`test_root_kustomization_leaves_dashboards_to_monitoring_stack`). Listing the perimeter in the root would bring back that SharedResourceWarning loop. The native path takes `_KUSTOMIZATIONS_BY_STACK["infra"] = (Path("monitoring"),)` instead, the #1297 pattern.
2. **The policy stays in `k8s/monitoring/kustomization.yaml` (key question 7 not applied).** Dropping it there would fail `test_kustomization_includes_networkpolicy[monitoring]`, which key question 6 keeps. It would also move live ownership between two Applications that both prune, and the `monitoring` Application could prune the perimeter before `base` adopts it.
3. **This reverses one choice of #1297 on purpose.** #1297 applied only `monitoring/dashboards` because the whole kustomization "would also apply `monitoring/networkpolicy.yaml`, which the native path never applied". Not applying it was this item's defect.
4. **Guard test, amended to the tree.**
   - The applied set is what `deploy-stack --stack all` applies without Argo CD: the root kustomization, every `_KUSTOMIZATIONS_BY_STACK` entry and every `_MANIFESTS_BY_STACK` file, over `_resolve_stacks("all")`.
   - Argo CD Application paths do not count as deploy paths. They appear only as the other path an exemption names. Counting them would have let the test pass before the fix.
   - The `devops` exemptions in the body are dropped. `_MANIFESTS_BY_STACK["devops"]` applies `devops-default-perimeter` and `roadmap-service-ingress`, so exempting them would fail the test's own "no exempted policy is applied" check.
   - otel stays exempt: Argo CD's `otel` Application syncs it, and deploy-stack does not.
   - The test fails at 910b823 for `('monitoring', 'monitoring-default-perimeter')` alone.
5. **Kustomizations are rendered with `kubectl kustomize`, not a hand-written walker.** The issue asked to generalise `_kustomize_services`, a hand-written walker of `resources` entries. Per the owner's library-over-hand-rolled rule, `tests/k8s_manifests.py` asks the real tool what `kubectl apply -k` applies, generators and the `namespace` transformer included, so the namespace fallback the old walker approximated is now exact. `_kustomize_services` is deleted and its test uses the shared helper. `kubectl` is already a test dependency (`tests/test_k8s_argocd_apps.py`) and runs offline on repository files.
   - Timing: rendering `k8s` and `k8s/monitoring` takes 0.04 s and 0.08 s on an idle devcontainer, and 0.35 s and 0.58 s at load average 22. The guard's call phase measured 0.29 s at load average 10.
   - Manifest files are parsed with `yaml.CSafeLoader`: the 91 YAML files under `k8s/` take 0.02 s, against 0.2 s with `SafeLoader`.
6. **`_kustomized_files` in `tests/test_k8s_llm_gateway.py` is left alone.** It answers a file-level question (does every manifest file under `k8s/llm` have a deploy path), which a render cannot answer. #795 also rewrites that file, and the issue's criteria do not include it.
7. **No CRD kinds in the `monitoring` kustomization.** A native deploy applies it before any chart installs CRDs (step 4 against step 9), and `kubectl apply -k` runs with `check=True`. A ServiceMonitor or PrometheusRule added there would stop a fresh native deploy. The kustomization's comment says so.
8. **Teardown needs no code.** `--stack all` runs `kubectl delete -k k8s`, which deletes namespace `monitoring`, and `--stack infra` deletes the namespace. Both take the policy with them, and a new parametrized test pins both commands.
9. **The functional live checks stay pending.** On homelab-k3s, Argo CD applies the perimeter and deploy-stack applies no manifests. Nothing records that #755 ran this item's functional checks: its task file and PR list none. So they remain person-run checks against the Argo-synced perimeter. The native path's checks need a cluster without Argo CD whose CNI enforces policy; the devcontainer's minikube enforces none (#990).
10. **The argocd and otel perimeters go to #1371 (key question 3).** That issue also owns both `0.0.0.0/0` ingress peers. Since #755, Argo CD's `otel` Application syncs the otel perimeter, so its 16686 world peer and its 8888 rule, which admits `monitoring` only while Traefik routes `otel-metrics-ingress` there, are live on clusters Argo CD manages.

## Acceptance Criteria
- [x] A native `deploy-stack --stack infra` (and `all`) applies `k8s/monitoring`, the perimeter and the dashboards, right after the root kustomization. `test_native_deploy_stack_infra_applies_the_monitoring_kustomization` pins the `kubectl apply -k` targets `[k8s, k8s/monitoring]`. `test_deploy_stack_dry_run_lists_the_kustomizations_its_stacks_apply` lists `k8s/monitoring` for `infra` and `all`, and nothing for `llm`. Both are in `tests/test_k8s.py`. The Argo CD path and the root kustomization are unchanged.
- [x] teardown-stack removes the perimeter with its namespace without new code. `test_teardown_stack_removes_the_monitoring_perimeter_with_its_namespace[all|infra]` asserts `kubectl delete -k k8s --ignore-not-found` and `kubectl delete namespace monitoring --ignore-not-found`.
- [x] `test_every_network_policy_has_a_deploy_stack_path_or_an_owned_exemption` (`tests/test_k8s_network_policies.py`) reads every NetworkPolicy under `k8s/` and compares it with the set deploy-stack applies. One tuple assertion checks three lists, all empty:
  - policies neither applied nor exempted;
  - exempted policies that are applied;
  - exempted policies missing from the file their exemption names.

  Each exemption names its file and the issue or path that owns it:
  - argocd: #1371;
  - otel: Argo CD's `otel` Application, and #1371 for deploy-stack;
  - `llm-gateway-perimeter`: #795;
  - `vllm-profiles-perimeter`: #820;
  - `portkey-perimeter` and `valkey-runs-perimeter`: Argo CD's `llm` Application, plus a person's apply for `devops ai runs`.
- [x] The tests use structural tuple assertions and reach no cluster, DNS or network. The only process they run is `kubectl kustomize` on repository files.
- [x] The alloy-operator pre-delete hook's API-server egress is pinned offline by `test_monitoring_network_policy_alloy_egress_rules` (6443 through the `ipBlock`, `tests/test_k8s_logging_stack.py`). The file has no ingress `ipBlock` (`test_monitoring_ingress_admits_no_world_cidr`).
- [x] `changelog.d/913.md` records the change under `### Security`; `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.
- Pending a person, before merge: `kubectl --context homelab-k3s diff -f k8s/monitoring/networkpolicy.yaml` prints nothing, because Argo CD's `monitoring` Application syncs this file with self-heal. Settle any difference: carry it into the file with a comment saying why, or drop it. A live-only rule is carried only if the checks below show the stack needs it.
- Pending a person, on homelab-k3s under the Argo-synced perimeter:
  - `kubectl --context homelab-k3s -n argocd get application monitoring` shows `Synced` and `Healthy`.
  - `kubectl --context homelab-k3s -n monitoring get networkpolicy monitoring-default-perimeter -o jsonpath='{.spec.ingress[*].from[*].ipBlock}'` prints nothing.
  - `kubectl --context homelab-k3s -n argocd get applications` shows `Healthy` for every Application that installs into `monitoring`.
  - `kubectl --context homelab-k3s -n monitoring logs -l app.kubernetes.io/name=alloy-metrics --since=1h` and the same for `alloy-logs` show no write errors.
  - Grafana's Prometheus, Loki, Jaeger and Pyroscope datasources pass "Save & test".
  - `kubectl --context homelab-k3s -n otel logs -l app.kubernetes.io/name=opentelemetry-collector --since=1h` shows no failed sends to Alloy on 9090.
  - Traefik's routes to Grafana, Prometheus and Alloy answer.
  - The Prometheus query `up == 0` returns no series.
  - `devops k8s configure-urls --addressing proxy --context homelab-k3s` still reaches Grafana and Prometheus while they run on the control-plane node (#953's caveat, `k8s/README.md`).
  - The next time the `k8s-monitoring` release is removed, its alloy-operator pre-delete hook Job completes: `kubectl --context homelab-k3s -n monitoring get jobs`.
- Pending a person, on a cluster without Argo CD whose CNI enforces NetworkPolicy:
  - Run `uv run devops k8s deploy-stack --stack infra --context <context>`.
  - `kubectl --context <context> -n monitoring get networkpolicy monitoring-default-perimeter` lists the policy.
  - The checks above pass, with Helm's `--wait` completing for every `monitoring` release.

## Deliverables
- [x] `src/devops_cli/commands/k8s/stack_lifecycle.py`: `_KUSTOMIZATIONS_BY_STACK["infra"]` is `monitoring`. Its comment says why the root leaves it out (#1279) and what the native apply brings (#913, #1297).
- [x] `tests/k8s_manifests.py`: `kustomized_objects` renders a kustomization with `kubectl kustomize`, and `manifest_objects` reads a manifest file. Both return (namespace, name) of one kind.
- [x] `tests/test_k8s_network_policies.py`: `UNDEPLOYED_NETWORK_POLICIES` and the guard test.
- [x] `tests/test_k8s_monitoring_integration.py`: the Service test uses `kustomized_objects`, and `_kustomize_services` is deleted.
- [x] `tests/test_k8s.py`: the native apply test is renamed and pins `k8s/monitoring`, the dry-run cases are updated, and the teardown test is new.
- [x] `k8s/monitoring/kustomization.yaml` names both apply paths and warns against CRD kinds. `k8s/monitoring/dashboards/kustomization.yaml` says it is applied through `k8s/monitoring`.
- [x] `k8s/README.md`:
  - the monitoring perimeter paragraph says which path applies it;
  - "Grafana Dashboards" names the `monitoring` kustomization;
  - the roadmap-service setup drops its manual perimeter step;
  - the directory tree says the monitoring kustomization lists the NetworkPolicy and dashboards, and the root lists the Service aliases.
- [x] `changelog.d/913.md`.
- The argocd and otel perimeters, and their `0.0.0.0/0` ingress peers: #1371.
