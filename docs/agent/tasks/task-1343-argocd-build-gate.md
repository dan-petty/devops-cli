# Task: Argo CD Application Build Gate and Live Report at Release Cut (#1343)

**Issue**: [#1343](https://github.com/dan-petty/devops-cli/issues/1343)
**Scope**: scope/release
**Feasibility**: Verified against local Argo CD applications in `k8s/argocd/apps` and `k8s/argocd/bootstrap`, `git archive` export behavior, `kubectl kustomize` execution against extracted archives, `argocd app diff` command surface with fake subprocess runner, and `cut_release` orchestration in `tests/test_release.py`.

## Description

A release cut must guarantee that every GitOps application managed by Argo CD builds deterministically at the release head before cutting the release. This deliverable (#1343) implements the complete offline deterministic Argo CD build gate and live non-blocking cluster diff and override report:
- Discovers all Argo CD `Application` resources across `k8s/argocd/apps` and `k8s/argocd/bootstrap` pointing to this repository (`CONST_K8S_ARGOCD_APPLICATION_DIRS`).
- Exports a clean snapshot of the release tip using `git archive` into an isolated temporary directory, ensuring uncommitted or gitignored files cannot mask broken kustomizations.
- Builds every path application using Kustomize (`build_manifest_path`) and verifies template domain placeholder safety: placeholders (`example.com`, `$DOMAIN`, etc.) are permitted only in host fields of homelab applications (`"devops"`, `"ingress"`), and are rejected in ConfigMaps, non-host fields, Helm value files, or non-homelab applications.
- Fails closed with typed `ArgoCDGateError` before any release branching, file modifications, commits, or pushes occur in `cut_release`.
- Executes a live, non-blocking Argo CD application diff report against the configured cluster: diffs each Application at the release tip SHA using `--grpc-web` (multi-source Applications use their git source position via `--source-positions`), with the token passed strictly via environment variable `ARGOCD_AUTH_TOKEN` (never in `argv`).
- Evaluates homelab application overrides: surfaces any template domain placeholder hosts at the tip lacking active live `test` operations alongside the remedial command (`devops k8s deploy-stack --stack <stack>`).
- Emits a single warning and proceeds without interruption if `argocd.url`, the authentication token, or the `argocd` CLI binary is absent.
- Documents the gate and live report in Step 2 of `RELEASE_CYCLE.md`.

## Acceptance Criteria

- [x] Every Argo CD `Application` pointing to this repository is discovered and validated.
- [x] Path applications are built using Kustomize from an exported archive of the release tip.
- [x] Template domain placeholder values outside allowed homelab host fields trigger gate failure.
- [x] Missing kustomization files, broken resources, or missing Helm value files raise `ArgoCDGateError`.
- [x] A gate failure prevents `cut_release` from creating branches, writing files, or pushing to origin.
- [x] With an Argo CD server configured, the cut reports each Application's diff at the release tip SHA with `--grpc-web`, multi-source Applications by their git source position, and the token appearing only in the environment.
- [x] Diff exit 1 is reported as "differs", exit 2 as "failed" with stderr truncated to `CONST_MAX_ERROR_DETAIL_LENGTH`, and neither halts the release cut.
- [x] Placeholder hosts at the tip not named by live `test` operations are reported with their `deploy-stack --stack` command.
- [x] Without `argocd.url`, token, or the `argocd` binary, one warning names what is missing and the cut continues.
- [x] `RELEASE_CYCLE.md` documents both the offline gate and the live report in Step 2.
- [x] Unit and integration tests verify offline validation and live reporting with a fake runner.
- [x] Changelog fragment `changelog.d/1343.md` added.

## Deliverables

- [x] Added `CONST_K8S_KUSTOMIZATION_NAMES` and `CONST_K8S_ARGOCD_APPLICATION_DIRS` in `src/devops_cli/config/constants.py`.
- [x] Added `ArgoCDGateError` in `src/devops_cli/exceptions/k8s.py`.
- [x] Added `holds_template_domain_value` and `build_manifest_path` in `src/devops_cli/k8s/template.py`.
- [x] Implemented `src/devops_cli/k8s/argocd_gate.py` with `check_argocd_gate`, `discover_argocd_applications`, and `discover_path_applications`.
- [x] Created `src/devops_cli/argo/credentials.py` for lifted server and token resolution and re-exported in `src/devops_cli/argo/__init__.py`.
- [x] Updated `src/devops_cli/commands/argo.py` to use `resolve_argocd_server_and_token`.
- [x] Implemented `src/devops_cli/k8s/argocd_live_report.py` with `report_argocd_live_diff`, `extract_live_tested_hosts`, and `_find_repo_source_position`.
- [x] Integrated `check_argocd_gate` and `report_argocd_live_diff` into `cut_release` in `src/devops_cli/release/cut.py`.
- [x] Updated `RELEASE_CYCLE.md` documenting the offline gate and live diff report.
- [x] Added `changelog.d/1343.md`.
- [x] Authored comprehensive tests in `tests/test_k8s_argocd_gate.py`, `tests/test_k8s_argocd_live_report.py`, `tests/test_k8s_argocd_apps.py`, and `tests/test_release.py`.
