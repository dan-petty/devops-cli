# Task #861: Supply-Chain Claims Made True

**Issue**: [#861](https://github.com/dan-petty/devops-cli/issues/861)
**Status**: Done
**Scope**: `docs/SDLC.md`, `src/devops_cli/commands/ci.py`, `src/devops_cli/commands/scan.py`, `src/devops_cli/security/zizmor.py`, `src/devops_cli/config/`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `pyproject.toml`, `uv.lock`, `tests/`
**Feasibility**: Checked against the tree at `release/v0.2.36` (76dd52a), following the issue's 2026-10-08 refinement, which retired the Dependabot retarget (Renovate replaced it) and moved SARIF upload to #419. `uvx zizmor@1.30.1 --offline --format json .github/` reported six `template-injection` findings in `release.yml` (one High at the dispatched `version` input) and none for `unpinned-uses` or `excessive-permissions`. A YAML walk of `.github/` found seven `${{ }}` expressions in five `run:` blocks (`release.yml` and `ci.yml`). `uv audit --offline` exits 2 and a clean `uv audit` exits 0, uv's error and success statuses; 1 is a check that failed. No Renovate-authored issue or pull request exists in the repository.

## Checklist
- [x] `docs/SDLC.md` claims no weekly Dependabot audits, `pip-audit` or SLSA Level 3, and names the controls the repository runs: `uv audit` in `devops ci`, `tools.lock` hashes, SHA-pinned actions, the zizmor gate and release provenance attestations. The Renovate line says what the configuration does and that Renovate acts only where its GitHub App is installed.
- [x] `devops ci maintain` runs the `audit` check's `uv audit` instead of the undeclared `pip-audit`, and reports exit 1 as vulnerabilities found and any other failure as an audit that could not run.
- [x] zizmor 1.30.1 is pinned in the dev group. `devops scan workflows` runs it offline with `--no-exit-codes`, shows every finding, and fails on `template-injection`, `unpinned-uses` and `excessive-permissions` (`CONST_ZIZMOR_BLOCKING_RULES`) or when zizmor could not run. `devops ci` runs it as the `zizmor` check, which CI's static analysis job runs.
- [x] No `run:` block interpolates a `${{ }}` expression: the five steps take their values through `env:`, and `ci.yml` reads the runner's `GITHUB_REPOSITORY`.
- [x] A contract test resolves every `devops` command in the workflows, composite actions and pre-commit hooks with `resolve_devops_argv`, with a negative control; others pin that no `run:` block holds an expression and that every remote `uses:` is pinned to a commit SHA.
- SARIF upload of zizmor findings waits for #419, as the refinement records.
- Pending a person: the repository setting that requires SHA-pinned actions (`sha_pinning_required`) and the Renovate GitHub App installation are repository settings outside this change.
