# Task: Discriminate Kubernetes Manifests for Kube-linter and Pluto Scans (#1242)

**Issue**: [#1242](https://github.com/dan-petty/devops-cli/issues/1242)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/ai

## Description

Prevent false static analyzer execution failures in review pipelines (`devops ai review branch`) for Kube-linter and Pluto when reviewing branches with deleted files or non-Kubernetes YAML files.
- Introduce `is_kubernetes_manifest(path)` in `devops_cli.security.kubeconform` and export it in `devops_cli.security`, validating file existence, supported extensions, bounded file size, and the presence of `apiVersion` in parsed documents.
- Pre-filter candidate Kubernetes manifest paths in `_run_static_scanners` and `_scan_kubernetes_manifests` (`pipeline.py`) via `_is_scannable_manifest`, skipping non-manifest YAML files (e.g. `.github/labels.yml`, GitHub Actions workflows) and deleted files in branch diffs while preserving compatibility with mocked scanner test harnesses.
- Ensure `build_command` in `KubelinterScanner` resolves target paths to absolute paths when present, matching `PlutoScanner`.
- Add comprehensive test coverage in `tests/test_review_static_analyzers.py`.
- Upgrade `multidict` from 6.8.0 to 6.9.1 in `uv.lock` resolving security advisory GHSA-54p9-h82j-f925.

## Acceptance Criteria

- [x] **Kubernetes manifest discrimination.** `is_kubernetes_manifest(path)` returns `True` for valid Kubernetes manifests (YAML or JSON) declaring `apiVersion`, and `False` for non-Kubernetes YAML files (e.g. `.github/labels.yml`, `.github/workflows/ci.yml`), non-existent files, and oversized files.
- [x] **Clean manifest scanning execution.** `_scan_kubernetes_manifests` filters candidate paths to valid manifests, ensuring missing files and non-manifest YAML files are bypassed cleanly without setting analyzer status to `failed`.
- [x] **Mock test harness compatibility.** `_is_scannable_manifest` supports mocked scanner test executions that supply non-existent dummy file paths.
- [x] **Security vulnerability remediation.** `uv.lock` upgraded for `multidict` to 6.9.1, passing `uv audit`.
- [x] **Changelog fragment.** `changelog.d/1242.md` created; `CHANGELOG.md` and `docs/ROADMAP.md` untouched.
- Pending a person: `uv run devops ci` passes on this branch.

## Deliverables

- [x] `src/devops_cli/security/kubeconform.py`: implement and export `is_kubernetes_manifest(path)`.
- [x] `src/devops_cli/security/__init__.py`: re-export `is_kubernetes_manifest`.
- [x] `src/devops_cli/security/kubelinter.py`: resolve `target_path` in `build_command`.
- [x] `src/devops_cli/ai/review/pipeline.py`: filter manifests in `_scan_kubernetes_manifests` and `_run_static_scanners` using `_is_scannable_manifest`.
- [x] `tests/test_review_static_analyzers.py`: add unit tests covering manifest discrimination, mock harness support, and deleted/non-k8s file skipping.
- [x] `uv.lock`: updated `multidict` to 6.9.1.
- [x] `changelog.d/1242.md`: record user-facing bug fix for Issue #1242.
