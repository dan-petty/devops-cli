# Task 1143: Review tools run at the project's declared language and platform versions and count only after their output on a canary matches the recorded expected output

**Issue**: [#1143](https://github.com/dan-petty/devops-cli/issues/1143)
**Feasibility**: Verified against live pinned binaries (`semgrep` 1.179.0 vs 1.178.0, `ruff` 0.16.8, `bandit` 1.9.4, `mypy` 2.3.1, `kube-linter` 0.8.3, `pluto` 5.24.4) inside the container runtime: `ruff check --target-version py314`, `mypy --python-version 3.14`, and `pluto detect-files --target-versions k8s=v1.37.1` accept declared project versions; Semgrep 1.179.0 parses PEP 758 unparenthesized `except ValueError, TypeError as exc:` and emits `("canary-pep758-tuple", 17)` while Semgrep 1.178.0 fails the canary with `("canary-pep758-as-binding", 17)`.

## Summary

Wired project language and Kubernetes version discovery into review static analysis tools (`ruff`, `mypy`, `pluto`) with `"coverage_gap"` reporting when a required project version declaration is absent, and added a 5-tuple cached canary verification gate (`(tool, version, binary_sha, language_version, ruleset_digest)`) across `semgrep`, `ruff`, `bandit`, `mypy`, `kube-linter`, and `pluto` that feeds both `admit(..., canary_passed=...)` and `coverage[tool][file]`.

## Deliverables

- [x] Resolve Ruff `--target-version` from `[tool.ruff].target-version` or `[project].requires-python` in `pyproject.toml`, Mypy `--python-version` from `[tool.mypy].python_version` or `[project].requires-python` in `pyproject.toml`, and Pluto `--target-versions k8s=<version>` from `kubernetes_version` in `.devops/review.toml`, reporting `ScanOutcome(status="coverage_gap", ...)` when a required declaration is missing.
- [x] Materialize deterministic canary fixtures (`CONST_CANARY_PYTHON_SOURCE` with PEP 758 `except ValueError, TypeError as exc:`, `CONST_CANARY_SEMGREP_PROBES_YAML`, `CONST_CANARY_MANIFEST_YAML`, `CONST_CANARY_DOCKERFILE_SOURCE`) and evaluate tool outputs as `(rule_id, line)` sets against `CONST_CANARY_EXPECTED_RESULTS`.
- [x] Cache canary outcomes per `(tool, version, binary_sha, language_version, ruleset_digest)` in `devops_cli.review.canary` and wire the cached boolean result into `ReviewPipelineOrchestrator` so it feeds both `admit(..., canary_passed=...)` (`rejection_counts["canary-failed"]`) and `coverage[tool][file] == "canary failed"`.
- [x] Record real tool outputs in [`recorded_outputs.json`](file:///home/vscode/.gemini/antigravity/worktrees/devops-cli/continue_with_implementation_for/tests/fixtures/review_canary/recorded_outputs.json) and verify all acceptance criteria in [`test_review_canary.py`](file:///home/vscode/.gemini/antigravity/worktrees/devops-cli/continue_with_implementation_for/tests/test_review_canary.py).
