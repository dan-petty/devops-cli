# Task 620: DevContainer Post-Create Automatically Bootstraps Missing DevOps Tools

**Issue**: [#620](https://github.com/dan-petty/devops-cli/issues/620)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Following devcontainer recreation or rebuild, users found that managed DevOps tool binaries (`k9s`, `trivy`, `kube-linter`, `popeye`, `pluto`, `kustomize`, `argo`, `argocd`, `kubectl-argo-rollouts`) were missing from developer shells, triggering errors such as `zsh: command not found: k9s`. While developer tools (`uv`, `pre-commit`, `claude`) and `gnome-keyring` were bootstrapped during `postCreateCommand` (`devops devcontainer post-create`), managed tool installation was omitted from the automated lifecycle.

Additionally, upstream tool releases had changed asset packaging and checksum conventions (`argo-workflows-cli-checksums.txt`, `argo-rollouts-checksums.txt`, and `kube-linter-linux.tar.gz`), breaking downloads on modern releases.

### Key Deliverables Completed:

- [x] **Automated Tool Bootstrapping in DevContainer Lifecycle** (`src/devops_cli/commands/devcontainer.py`):
  - Added `_bootstrap_managed_tools` helper delegating to `install_managed_tools(target_dir=dest, only_missing=True)`.
  - Wired into `_run_post_create_lifecycle` alongside `_bootstrap_developer_tools` and `_install_keyring_packages`.
  - Installs binaries to `~/.local/bin`, persisting them across container stops, restarts, and rebuilds via the `global-devcontainer-home` named volume.
  - Added `--skip-tools` CLI option to `devops devcontainer post-create` and honored `DEVOPS_CLI_SKIP_TOOL_BOOTSTRAP` for fast hermetic test isolation.
- [x] **Zero-Overhead Tool Resolution & Missing-Only Support** (`src/devops_cli/commands/install_tools.py`):
  - Added `is_tool_installed(spec, target_dir)` checking both target directory existence and system `PATH` via `shutil.which`. Tools already present incur zero download penalty or delay.
  - Added `--only-missing` flag to `devops install-tools` callback, filtering target tools to only those not yet installed.
  - Decomposed `install_all` into single-responsibility helpers (`_validate_install_args`, `_resolve_install_targets`, `_install_single_target`, `is_tool_installed`), bringing cyclomatic complexity well within architectural limits ($M \le 10$, depth $\le 5$).
  - Exposed programmatic helper `install_managed_tools(target_dir, only_missing=True) -> list[str]`.
- [x] **Upstream Release Asset Modernization & Checksum Fallbacks** (`src/devops_cli/commands/install_tools.py`):
  - Updated `_install_argo` with `_resolve_argo_expected_checksum` supporting consolidated `argo-workflows-cli-checksums.txt` and legacy `.sha256`.
  - Updated `_install_rollouts` with `_resolve_rollouts_expected_checksum` supporting `argo-rollouts-checksums.txt` and fallback to `sha256checksums.txt`.
  - Updated `_install_kubelinter` to test modern unarchived release names (`kube-linter-linux.tar.gz` on amd64, `kube-linter-linux_arm64.tar.gz` on arm64) with fallback to `kube-linter-linux-{_ARCH}.tar.gz`.
  - Updated `kubectl` version command from deprecated `--short` to modern `["kubectl", "version", "--client"]`.
- [x] **Automated Tests & Quality Gates** (`tests/test_install_tools.py`, `tests/test_devcontainer.py`):
  - Refactored monolithic installer tests into focused, low-complexity modules with structural tuple equality assertions.
  - Added unit test suites verifying `is_tool_installed`, `install-tools --only-missing`, programmatic `install_managed_tools`, `_bootstrap_managed_tools` lifecycle behaviors, and `post-create --skip-tools`.
  - 100% pass across all tests and Gated CI validation suite (`uv run devops ci`).
