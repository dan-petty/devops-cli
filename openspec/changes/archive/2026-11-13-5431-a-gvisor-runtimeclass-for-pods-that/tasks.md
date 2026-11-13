# Tasks

## 1. Declare RuntimeClass gvisor in the environment tree

Kind: manifest. Changes: `k8s/runtimeclass-gvisor.yaml`, `k8s/kustomization.yaml`, `tests/invariants/test_k8s_argocd_apps.py`.

- [x] 1.1 `tests/invariants/test_k8s_argocd_apps.py::test_the_gvisor_runtime_class_runs_pods_only_on_labelled_nodes` fails: the root kustomization does not list `runtimeclass-gvisor.yaml`.
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_argocd_apps.py` fails on the base
- [x] 1.2 Add `k8s/runtimeclass-gvisor.yaml` with RuntimeClass `gvisor`, handler `runsc` and `scheduling.nodeSelector` `node-restriction.kubernetes.io/gvisor: "true"`, and list it in the resources of `k8s/kustomization.yaml`.
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_argocd_apps.py` passes

## 2. Documents

Kind: other. Changes: `k8s/README.md`, `docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md`.

- [x] 2.1 Add the section "gVisor Runtime" and the directory line of the file to `k8s/README.md`, with the node label, the node setup of the infra repository, the use of `runtimeClassName: gvisor`, the seccomp limit and the measurement of #5434 before a workload uses the class.
  - Verification: `$ uv run devops ci docs`
- [x] 2.2 Add the Status History line "Fact out of date" for the RuntimeClass to ADR 0018, and change no other line of the record.
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py tests/docs/test_docs_adr_records.py`

## Workflow follow-up

- #5434 (a sub-issue of #2695): the measurement of `runc` against `runsc` on the labelled node. It sets `overhead.podFixed` of the class and decides whether the runner Jobs use it.
- #4003 and #5356: the run Job of the planner and the in-cluster browser set `runtimeClassName: gvisor` after the measurement. The admission policy of the Service Jobs gets a row for `runtimeClassName` in the same item.
- #5435: `devops infra plan` shows a skip by a `when` that names `ansible_check_mode` as unchecked. The apply of the gVisor play of the infra repository needs it, because check mode cannot install `runsc` from a new apt source.
- Pending a person: merge the pull request of the infra repository that installs the pinned `runsc` and sets the node label, then apply it.
