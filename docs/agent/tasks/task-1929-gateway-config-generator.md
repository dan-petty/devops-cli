# Task: A Changed Gateway Config Rolls the Gateway Deployment, So deploy-stack Never Leaves a Stale Pod (#1929)

**Issue**: [#1929](https://github.com/dan-petty/devops-cli/issues/1929)
**Scope**: scope/k8s
**Feasibility**: On 2026-10-23, Argo CD (Application `llm`, `status.sourceType: Kustomize`, path `k8s/llm`, Argo CD v3.5.3) synced the changed `k8s/llm/gateway/configmap.yaml` of #1987, but the gateway pod kept the old config until a person ran `kubectl -n llm rollout restart deployment/llm-gateway`. The Deployment mounts the ConfigMap with `subPath`, which never gets an update, and LiteLLM reads its config only at start. deploy-stack applied each gateway file with `kubectl apply -f` (`_MANIFESTS_BY_STACK["llm"]`). Kustomize's `configMapGenerator` is the open tool: `kubectl kustomize` (Kustomize v5.8.1) of `k8s/llm` and of `k8s/llm/gateway` gives ConfigMap `llm-gateway-config-<hash>` and writes that name into the Deployment's config volume. `k8s/monitoring/dashboards/kustomization.yaml` already generates the Grafana dashboard ConfigMaps in the same way, without the hash.

## Description
The gateway's LiteLLM config moves from the inline `config.yaml` key of `k8s/llm/gateway/configmap.yaml` to its own file, `k8s/llm/gateway/config.yaml`, with all its comments. The new `k8s/llm/gateway/kustomization.yaml` generates ConfigMap `llm-gateway-config` from that file. Kustomize gives the name a hash of the content and writes the hashed name into the Deployment. A changed config thus changes the pod template, and Kubernetes rolls the gateway onto it. No `kubectl rollout restart` is necessary, and deploy-stack runs none.

Argo CD renders `k8s/llm`, which now lists the `gateway` directory, so it gets the generated ConfigMap and prunes the old one. Without Argo CD, `devops k8s deploy-stack --stack llm` applies the directory with `kubectl apply -k k8s/llm/gateway`, in the place of the four gateway files, after the Secret push and before the charts. `teardown-stack` deletes it with `kubectl delete -k`. A path of `_MANIFESTS_BY_STACK` can now be a file (`-f`) or a kustomization directory (`-k`). The ServiceMonitor stays outside the gateway kustomization and is applied after the charts, because it needs the `monitoring.coreos.com` CRDs (#1367).

## Key Changes
- **`k8s/llm/gateway/config.yaml`**: the LiteLLM config, as it was in the ConfigMap.
- **`k8s/llm/gateway/kustomization.yaml`**: the NetworkPolicy, Deployment and Service, the `configMapGenerator` with the ConfigMap's labels, and `sortOptions` that apply the NetworkPolicy and the ConfigMap before the Deployment (#795).
- **`k8s/llm/gateway/configmap.yaml`**: removed.
- **`k8s/llm/kustomization.yaml`**: lists `gateway` and `gateway/servicemonitor.yaml`.
- **`src/devops_cli/commands/k8s/stack_lifecycle.py`**: `_MANIFESTS_BY_STACK["llm"]` names `k8s/llm/gateway`. `_apply_single_manifest` applies a directory with `kubectl apply -k`, and `teardown-stack` deletes a directory with `kubectl delete -k`.
- **`src/devops_cli/config/defaults.py`**, **`src/devops_cli/commands/ai_gateway.py`**, **`src/devops_cli/ai/gateway_render.py`**: `DEFAULT_LLM_GATEWAY_CONFIG_PATH` is `k8s/llm/gateway/config.yaml`. `devops ai gateway render` reads and writes that file, and its `--configmap` option is now `--config`. The renderer finds the sections and the `model_list` entries at the indent of the plain file.
- **`tests/k8s_manifests.py`**: `applied_documents` and `applied_objects` read a path of deploy-stack's tables as deploy-stack applies it: a directory through `kubectl kustomize`, a file as it is. The tests that read `_MANIFESTS_BY_STACK` use them.
- **`k8s/README.md`**, **`k8s/llm/profiles/README.md`**, **`k8s/llm/values-open-webui.yaml`**, **`docs/CLI_REFERENCE.md`**, **`docs/commands/ai.md`**: name `config.yaml`, describe the roll, and the new option. The person step of #1987 no longer asks for a gateway restart.

## Acceptance Criteria
- [x] The render of `k8s/llm` (Argo CD) and of `k8s/llm/gateway` (deploy-stack) gives the gateway ConfigMap `llm-gateway-config-<hash>` that holds `config.yaml`, and the Deployment's config volume names it (`test_the_gateway_mounts_a_config_map_named_by_a_hash_of_its_config`).
- [x] A change to `config.yaml` alone changes the pod template, only in the name of the config volume's ConfigMap (`test_a_changed_gateway_config_changes_only_the_config_map_name_in_the_pod_template`).
- [x] Without Argo CD, deploy-stack pushes the Secrets, then runs `kubectl apply -k k8s/llm/gateway`, then applies the ServiceMonitor after the charts; teardown-stack runs `kubectl delete -k k8s/llm/gateway` (`tests/test_k8s.py`). Neither runs `kubectl rollout restart` for the gateway.
- [x] `devops ai gateway render` finds `k8s/llm/gateway/config.yaml` up to date (`test_rendered_gateway_config_matches_ollama_profiles`).
- Pending a person: after Argo CD syncs the merge, `kubectl -n llm get deploy llm-gateway -o jsonpath='{.spec.template.spec.volumes[0].configMap.name}'` prints `llm-gateway-config-<hash>`, `kubectl -n llm get configmap -l app.kubernetes.io/name=llm-gateway` lists only that ConfigMap, and `kubectl -n llm rollout status deployment/llm-gateway` completes. This first sync rolls the gateway once.

## Trade-offs
- Without Argo CD, each config change leaves the ConfigMap of the old config in the cluster, because `kubectl apply -k` does not prune. It is small, and `teardown-stack` deletes it with the namespace.
- The gateway kustomization holds no ServiceMonitor, so `kubectl apply -k k8s/llm/gateway` works on a cluster without the monitoring CRDs. Argo CD gets the ServiceMonitor from `k8s/llm/kustomization.yaml`.
