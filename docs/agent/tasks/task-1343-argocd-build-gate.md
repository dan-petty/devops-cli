# Task: Argo CD Application Build Gate at Release Cut (#1343)

**Issue**: [#1343](https://github.com/dan-petty/devops-cli/issues/1343)
**Scope**: scope/release
**Feasibility**: Verified against local Argo CD applications in `k8s/argocd/apps` and `k8s/argocd/bootstrap`, `git archive` export behavior, `kubectl kustomize` execution against extracted archives, and `cut_release` orchestration in `tests/test_release.py`.

## Description

A release cut must guarantee that every GitOps application managed by Argo CD builds deterministically at the release head before cutting the release. This deliverable (Part 1 of #1343) implements the offline deterministic Argo CD build gate:
- Discovers all Argo CD `Application` resources across `k8s/argocd/apps` and `k8s/argocd/bootstrap` pointing to this repository (`CONST_K8S_ARGOCD_APPLICATION_DIRS`).
- Exports a clean snapshot of the release tip using `git archive` into an isolated temporary directory, ensuring uncommitted or gitignored files cannot mask broken kustomizations.
- Builds every path application using Kustomize (`build_manifest_path`) and verifies template domain placeholder safety: placeholders (`example.com`, `$DOMAIN`, etc.) are permitted only in host fields of homelab applications (`"devops"`, `"ingress"`), and are rejected in ConfigMaps, non-host fields, Helm value files, or non-homelab applications.
- Fails closed with typed `ArgoCDGateError` before any release branching, file modifications, commits, or pushes occur in `cut_release`.
- Updates `RELEASE_CYCLE.md` documenting the gate in Step 2 of the release procedure.

## Acceptance Criteria

- [x] Every Argo CD `Application` pointing to this repository is discovered and validated.
- [x] Path applications are built using Kustomize from an exported archive of the release tip.
- [x] Template domain placeholder values outside allowed homelab host fields trigger gate failure.
- [x] Missing kustomization files, broken resources, or missing Helm value files raise `ArgoCDGateError`.
- [x] A gate failure prevents `cut_release` from creating branches, writing files, or pushing to origin.
- [x] `RELEASE_CYCLE.md` documents the Argo CD build gate in Step 2.
- [x] Unit and integration tests verify pass and failure conditions across all application permutations.
- Live Argo CD diff and override report after the offline gate (closes #1343 in follow-up PR).

## Deliverables

- [x] Added `CONST_K8S_KUSTOMIZATION_NAMES` and `CONST_K8S_ARGOCD_APPLICATION_DIRS` in `src/devops_cli/config/constants.py`.
- [x] Added `ArgoCDGateError` in `src/devops_cli/exceptions/k8s.py`.
- [x] Added `holds_template_domain_value` and `build_manifest_path` in `src/devops_cli/k8s/template.py`.
- [x] Implemented `src/devops_cli/k8s/argocd_gate.py` with `check_argocd_gate`, `discover_argocd_applications`, and `discover_path_applications`.
- [x] Integrated `check_argocd_gate` into `cut_release` in `src/devops_cli/release/cut.py`.
- [x] Documented the Argo CD build gate in `RELEASE_CYCLE.md`.
- [x] Added comprehensive tests in `tests/test_k8s_argocd_gate.py` and `tests/test_release.py`, and updated `tests/test_k8s_argocd_apps.py`.
