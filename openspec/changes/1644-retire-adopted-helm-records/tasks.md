# Tasks

## 1. The command retires the records of adopted releases

- [x] Add failing tests: a release qualifies by tracking id or by the `argocd-controller` field manager; a release with an object that only Helm applied does not qualify and names it; a copy with an owner reference does not count; an operator's record and an unrendered release stay; the plan writes nothing and reads no Secret data; `--confirm` deletes the planned records by name; `--dry-run` starts no process; a failed kubectl request stops the command and deletes nothing
  - Verification: `uv run devops ci test tests/test_argo_helm_records.py`
- [x] Add `src/devops_cli/argo/helm_records.py` and the command `devops argo cd apps retire-helm-records`, with its help and messages in `lang/en/`
  - Verification: `uv run devops ci test tests/test_argo_helm_records.py tests/test_argo.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Argo CD reports a left-over record, and no runbook runs Helm against an adopted release

- [x] Change the pin in `tests/test_k8s_argocd_apps.py` so that it fails while AppProject `homelab` ignores `sh.helm.release.v1.*`, and add the knowledge base check
  - Verification: `uv run devops ci test tests/test_k8s_argocd_apps.py tests/test_argo_helm_records.py`
- [x] Remove the `sh.helm.release.v1.*` orphan ignore from `k8s/argocd/apps/projects.yaml`, and change `it_domains/tools/helm.md` so that its examples use a release that no Application renders and it sends adopted releases to Argo CD
  - Verification: `uv run devops ci test tests/test_k8s_argocd_apps.py tests/test_argo_helm_records.py`
- [x] Add the retirement step to the end of "Bootstrap & Adoption" and of "Recovery" in `k8s/README.md`
  - Verification: `uv run devops ci docs`

## 3. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1644-retire-adopted-helm-records`

## Workflow follow-up

- Pending a person: sync Application `prometheus-operator-crds` once (`devops argo cd apps sync prometheus-operator-crds`), so that Argo CD applies its 10 CustomResourceDefinitions. Server-side apply keeps their `helm.sh/resource-policy: keep`.
- Pending a person: run `devops argo cd apps retire-helm-records`, check the plan, then run it with `--confirm`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
