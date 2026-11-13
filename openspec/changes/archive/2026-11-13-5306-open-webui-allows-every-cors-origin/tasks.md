# Tasks

## 1. Data values of a ConfigMap

Kind: behavior.

- [x] 1.1 Write the failing tests: `host_patches` tests and then replaces each data value of a ConfigMap that holds the placeholder, and no annotation, binary data or other value; the Argo CD gate refuses the placeholder in an annotation of a ConfigMap of `devops`, and allows it in a data value.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_argocd_overrides.py tests/k8s/test_k8s_argocd_gate.py`
- [x] 1.2 Extend `_host_fields` in `src/devops_cli/k8s/argocd_overrides.py` with the data values of a ConfigMap.
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_argocd_overrides.py tests/k8s/test_k8s_argocd_gate.py`

## 2. Origins of Open WebUI

Kind: behavior.

- [x] 2.1 Write the failing tests: on a cluster that Argo CD manages, `deploy-stack --stack infra` sets `CORS_ALLOW_ORIGIN` of ConfigMap `llm/open-webui-origins` to `https://chat.<configured domain>` on the Application `ingress`; without Argo CD, `deploy-stack --stack llm` applies the origins under the configured domain before release `open-webui`; a check of the `k8s` row keeps the origins equal to the HTTPS origins of the hosts of Ingress `llm/open-webui-ingress`, before and after the patches, and finds the reference in `extraEnvFrom`.
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py`
- [x] 2.2 Add `k8s/ingress/open-webui-origins.yaml` to `k8s/ingress/kustomization.yaml` and to `MANIFESTS_BY_STACK["llm"]`, reference it from `extraEnvFrom` of `k8s/llm/values-open-webui.yaml`, and let the Valkey test accept a second `extraEnvFrom` entry.
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py tests/k8s/test_k8s_valkey_stack.py tests/invariants/test_k8s_argocd_apps.py`
- [x] 2.3 Run the `k8s` row with the new check.
  - Verification: `$ uv run devops ci --check --only k8s`

## 3. Documents

Kind: other.

- [x] 3.1 Add the row of ConfigMap data values to "Homelab Values at Deploy Time" in `k8s/README.md`, name the ConfigMap in the paragraph about the patches, tell when Open WebUI reads its origins and how they change, and add the file to the folder tree.
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- Pending a person: before the merge, stage the origins with `uv run devops k8s deploy-stack --stack infra --argocd-revision <head of the pull request>`, so that Open WebUI does not start with the placeholder origins.
- Pending a person: after the merge, the start log of Open WebUI in Loki (`{namespace="llm", container="open-webui"} |= "CORS_ALLOW_ORIGIN"`) has no `CORS_ALLOW_ORIGIN IS SET TO '*'` line, and `kubectl -n llm get configmap open-webui-origins -o jsonpath='{.data.CORS_ALLOW_ORIGIN}'` shows the two origins under the configured domain.
- Pending a person: after the merge, the chat page at `https://chat.<domain>` loads, and its Socket.IO connection opens with no `is not an accepted origin` line in the log of Open WebUI.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
