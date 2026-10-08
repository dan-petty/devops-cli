# Task: deploy-stack Applies the LLM Gateway's NetworkPolicy, Whose Egress Admits Only the Gateway's Backends (#795)

**Issue**: [#795](https://github.com/dan-petty/devops-cli/issues/795)
**Status**: Done
**Milestone**: v0.2.29
**Priority**: priority/p1-high
**Scope**: scope/k8s

## Description
The owner reduced this item's scope on 2026-10-08, and this change delivers the reduced scope. It covers the gateway policy only: deploy-stack applies it, and its egress loses the selectors that match no pod and the private-range ipBlock rule. The egress test stops pinning the dead names and reads its backends from the manifests. #1042's live `nvidia.com/gpu.architecture` selectors on `ollama-24gib`, `ollama-48gib` and `ollama-48gib-slow` stay as they are (option 1 of the 2026-10-03 owner-decision comment). The rest of the original body moves to #1367 (listed under Deliverables).

- **Deploy path.** `_MANIFESTS_BY_STACK["llm"]` (`src/devops_cli/commands/k8s/stack_lifecycle.py`) lists `k8s/llm/gateway/networkpolicy.yaml` after the gateway ConfigMap and before its Deployment. `deploy-stack --stack llm` and `--stack all` therefore apply `llm-gateway-perimeter` on a cluster without Argo CD, and `teardown-stack` deletes it, since teardown walks the same list in reverse. The `llm` Argo CD Application already syncs the file through `k8s/llm/kustomization.yaml` (#755). It tracks `main`, so the narrowed policy reaches an Argo CD cluster once the release merges. deploy-stack does not read the result of each `kubectl apply` (`_apply_single_manifest`), so the order guarantees only that the policy is applied first. The Deployment does not wait for it, and the original criterion's wording "never starts the gateway without its policy" is dropped.
- **Egress.** The policy loses three things:
  - the `app.kubernetes.io/name: ollama` selector, whose source was the deleted `values-ollama.yaml` (#953);
  - the `ollama-volta-1` selector, which no manifest sets;
  - the ipBlock rule that admitted the RFC 1918 ranges on 11434 and 8000. kube-router matches an ipBlock against pod addresses, so that rule admitted every pod on those ports and made the selectors above it pointless.

  Egress now admits these:
  - the Ollama tiers (`llm.devops.io/provider: ollama`, TCP 11434);
  - Valkey (`app.kubernetes.io/name: valkey`, TCP 6379);
  - DNS to `kube-system` (UDP and TCP 53);
  - the vLLM rule, which #820 deletes.

  Ingress is unchanged: TCP 4000 from any source. A comment in the policy says why it names no ipBlock. Every gateway backend is an in-cluster Service: the four Ollama alias Services the ConfigMap names (`ollama-16gib-fast`, `ollama-48gib-fast`, `ollama-48gib-slow`, `ollama-64gib-standard`) and `valkey`. No Ollama tier uses the host network.
- **Coordination with #913.** #913's guard test exempted `("llm", "llm-gateway-perimeter")` under #795. #913 merged second and kept the exemption, so it was deleted on `release/v0.2.29` once both had landed, and the guard test now checks that deploy-stack applies the policy.

## Acceptance Criteria
- [x] `_MANIFESTS_BY_STACK["llm"]` lists `k8s/llm/gateway/networkpolicy.yaml` before `gateway/deployment.yaml`, and `teardown-stack` deletes it. `tests/test_k8s.py::test_llm_stack_applies_the_gateway_policy_before_the_gateway_and_deletes_it` runs both dry runs under `forbid_requests` and asserts the `manifests` order, the `manifest_deletes` entry, and that no request is made. On the base revision it fails with `(0, 0, False, False, []) != (0, 0, True, True, [])`.
- [x] The gateway's egress admits only the Ollama tiers on TCP 11434, Valkey on TCP 6379, DNS to `kube-system` on UDP and TCP 53, and the vLLM rule #820 removes. The `ollama-volta-1` selector, the `app.kubernetes.io/name: ollama` selector and the ipBlock rule are gone. Ingress stays TCP 4000 from any source.
- [x] `tests/test_k8s_llm_gateway.py::TestK8sLLMGatewayManifests::test_gateway_egress_admits_all_backends_in_configmap` reads its backends from the files: every ConfigMap `api_base` (`urllib.parse.urlsplit`), plus `LITELLM_REDIS_HOST` and `LITELLM_REDIS_PORT` from the gateway Deployment. It resolves each one against the `<name>.<namespace>.svc.cluster.local` name of every Service under `k8s/llm`. It fails when a backend is not such a Service, or when the Service has no selector or no numeric targetPort on the called port. It also fails when no egress rule has a podSelector whose `matchLabels` are a subset of the Service's selector on that targetPort. Removing the Ollama rule, or moving Valkey to another port, makes it name the affected backends.
- [x] `test_gateway_egress_admits_nothing_else` asserts that `_egress_violations` returns nothing for the real policy. That helper checks five things:
  - the policy selects the gateway's pod labels and enforces `Egress`;
  - every rule has a non-empty `to` and `ports`;
  - no peer is an ipBlock;
  - a podSelector peer stands alone and has `matchLabels` but no `matchExpressions`;
  - each peer is one of three kinds: a subset of a backend Service's selector, on those backends' TCP targetPorts only; one of the three vLLM selectors in `_VLLM_SELECTORS`, on TCP 8000; or the kube-system DNS peer, on exactly UDP and TCP 53.

  On the base revision the test fails, listing the two dead selectors and the three ipBlock peers. `test_each_widening_edit_is_a_violation` applies seven edits to a copy of the policy:
  - an ipBlock rule (an RFC 5737 range stands in, since any ipBlock fails);
  - a `podSelector: {}` peer;
  - the `app.kubernetes.io/name: ollama` selector;
  - a `namespaceSelector: {}` peer;
  - a rule without `ports`;
  - 6379 on the Ollama rule;
  - `Egress` removed from `policyTypes`.

  Each edit yields at least one violation.
- [x] `rg -n ollama-volta k8s src tests` prints nothing.
- [x] The tests read files, or run the CLI in dry-run mode with every subprocess, keyring and socket call refused. Each test's call phase stays under 1 s, and the egress inputs are read once per module.
- Pending a person: once the release merges and Argo CD syncs the `llm` Application, or after `uv run devops k8s deploy-stack --stack llm` on a cluster without Argo CD:
  - `kubectl -n llm get networkpolicy llm-gateway-perimeter -o jsonpath='{.spec.egress[*].to[*].ipBlock}'` prints nothing.
  - With `kubectl -n llm port-forward svc/llm-gateway 4000:4000` running and `KEY` set to the gateway's master key:
    - `curl -sS -H "Authorization: Bearer $KEY" http://localhost:4000/v1/models` lists the models;
    - `curl -sS -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' http://localhost:4000/v1/chat/completions -d '{"model":"devops-chat","messages":[{"role":"user","content":"ping"}]}'` returns a completion;
    - `curl -sS -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' http://localhost:4000/v1/embeddings -d '{"model":"bge-m3:latest","input":"ping"}'` returns an embedding.
  - `kubectl -n llm logs deploy/llm-gateway --since=15m | grep -ciE '(error|exception|refused|timeout).*(redis|valkey|ollama)|connecterror'` prints 0. It counts only error lines, so normal startup lines that mention Redis do not count.
  - If a route fails, revert this change. The removed ipBlock rule was the only one that did not depend on pod labels.

## Deliverables
- [x] `k8s/llm/gateway/networkpolicy.yaml`: the dead selectors and the ipBlock rule are removed, and a comment says why the policy names no address range.
- [x] `src/devops_cli/commands/k8s/stack_lifecycle.py`: the policy is in the `llm` stack's manifest list, before the gateway Deployment.
- [x] `tests/test_k8s_llm_gateway.py`: the derived backend test, the violations helper, and the seven widening cases.
- [x] `tests/test_k8s.py`: the deploy and teardown dry-run test.
- [x] `changelog.d/795.md` under `### Security`.
- The following parts of the original body moved to #1367:
  - the deploy-stack warning for GPU nodes without a usable `nvidia.com/gpu.total-vram-gib` (and, for the split tiers, `nvidia.com/gpu.architecture`) label;
  - the `k8s/README.md` GPU placement section, including what the gateway policy admits;
  - removal of the commented-out `gpu.architecture`/`gpu.family` selector blocks (six lines in each of six DaemonSets);
  - the move of the gateway's ServiceMonitor from `k8s-monitoring-values.yaml` `extraObjects` to the llm stack.
