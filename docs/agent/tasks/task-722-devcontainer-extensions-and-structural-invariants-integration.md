# Task 722: Configure DevContainer Extensions and Integrate Structural Invariants Sentinel

**Issue**: [#722](https://github.com/dan-petty/devops-cli/issues/722)
**Status**: Done
**Milestone**: `v0.2.24`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/cli`, `priority/p2-medium`

---

## 1. Description & Objectives

This task addresses workspace extension configuration, elimination of Continue.dev remnants, and the architectural integration of the AST structural invariants pre-commit sentinel directly into the `devops_cli` source tree.

### Key Deliverables Completed:
- [x] **DevContainer & VS Code Extension Configuration**:
  - Configured requested developer and agent extensions in `.devcontainer/devcontainer.json`:
    - `DavidAnson.vscode-markdownlint` (configured markdown formatting and linting rules)
    - `rust-lang.rust-analyzer` (configured default rust formatter and clippy check command)
    - `firefox-devtools.vscode-firefox-debug` (configured for client/desktop UI execution)
    - `ms-windows-ai-studio.windows-ai-studio` (installed and active)
    - `kilocode.Kilo-Code` (installed and active)
    - `saoudrizwan.claude-dev` (Cline) (installed and active)
  - Configured `ollama.endpoint` and `ollama.model` in `.devcontainer/devcontainer.json` and `.vscode/settings.json`.
- [x] **Elimination of Continue.dev Remnants**:
  - Completely removed legacy Continue.dev workspace configurations, stubs, and test references.
  - Reverted agent scaffolding in `tests/test_instruction_generator.py` with structural tuple equality checks adhering to $M \le 10$ complexity invariants.
- [x] **Integration of Structural Invariants Sentinel**:
  - Relocated and integrated the standalone AST structural invariants sentinel from `/scripts` into `src/devops_cli/security/structural_invariants.py`.
  - Completely deleted the `/workspaces/devops-cli/scripts` directory, satisfying the zero stray scripts mandate.
  - Updated `.pre-commit-config.yaml` to run `uv run python3 -m devops_cli.security.structural_invariants`.
  - Updated `tests/test_structural_invariant_hook.py` to test `devops_cli.security.structural_invariants`.
  - Added gate assertion in `tests/test_architectural_invariants.py` ensuring neither stray scripts nor `scripts/` directory exist in the repository root.
- [x] **Cache Cleanup & Ignore Hygiene**:
  - Removed ephemeral `.grimp_cache/` and `.import_linter_cache/` directories.
  - Added `.kilo/`, `.grimp_cache/`, and `.import_linter_cache/` to `.gitignore`.
- [x] **vLLM Workload Profiles & Auto Tool Choice Configuration**:
  - Configured `--enable-auto-tool-choice` and `--tool-call-parser` (`hermes` for Qwen/DeepSeek-Distill-Qwen profiles, `llama3_json` for DeepSeek-Distill-Llama profile) across all inference tiers in `k8s/llm/profiles/vllm-profiles.yaml`.
  - Added structural assertions in `tests/test_k8s_llm_gateway.py` validating that vLLM profile args enforce `--enable-auto-tool-choice` and `--tool-call-parser`.
  - Applied updated manifests to cluster (`kubectl apply -f k8s/llm/profiles/vllm-profiles.yaml -n llm`) and verified zero-downtime rolling update.
- [x] **vLLM & Ollama Dynamic DaemonSet Workload Scheduling**:
  - Migrated inference workload profiles (`vllm-profiles.yaml` and `ollama-profiles.yaml`) from manually replica-gated Deployments to Kubernetes DaemonSets.
  - Eliminated rigid GPU count constraints (`nvidia.com/gpu.count`) across all profiles in favor of pure GPU microarchitecture separation (`In` vs `NotIn` `["ada-lovelace", "ampere", "blackwell", "hopper"]`) and total VRAM capacity (`nvidia.com/gpu.total-vram-gib`).
  - Applied De Morgan's Boolean logic to Ollama node affinity to prevent false scheduling on modern GPU nodes lacking family labels.
  - Updated gateway and proxy test suites (`tests/test_k8s_llm_gateway.py`, `tests/test_k8s.py`, `tests/test_k8s_squid.py`) with structural assertions for DaemonSet workloads and dynamic total VRAM selection.
  - Applied DaemonSets to cluster and verified 1/1 Running state across all active hardware nodes (`vllm-16gib`, `vllm-48gib`, `ollama-24gib`, `ollama-64gib`).
- [x] **Review Findings Remediation & Review Engine Self-Improvement**:
  - Remediated verified and actionable code findings from `.data/reviews/20260929-053048`:
    - `install_tools.py`: Narrowed exception handling in `_resolve_argo_expected_checksum` and `_resolve_rollouts_expected_checksum` to `(httpx2.HTTPError, ValidationError, ToolDownloadError)` and validated token boundaries defensively.
    - `tracer.py`: Narrowed exception handling in `_resolve_git_dir_from_file` to `(OSError, RuntimeError)`.
    - `constants.py` & `analyze.py`: Declared `CONST_SAFE_GIT_REF_PATTERN` and `CONST_SAFE_GIT_RELPATH_PATTERN` in constants submodule and adopted in `_fetch_git_file_content` and `_resolve_merge_base` to prevent refspec manipulation or command splitting.
    - `pr.py`: Handled enum and string check buckets consistently in `_format_bucket_badge` and added error handling in `_validate_pr_ready_checks`.
    - `runner.py`: Switched backoff jitter to `secrets.SystemRandom()` for cryptographically secure, uncorrelated full jitter.
    - `gitleaks.py`: Sanitized debug log message format string and added `# nosec` to eliminate false secret leak alerts.
    - `review_environment.py`: Configured `PYTHONPATH` in bubblewrap sandbox execution and enhanced `_is_tautological_verification_command` to detect trivial import-only criteria.
    - `verify_finding_system.md`: Extended verification system prompt to invalidate hallucinations regarding JSON parsing exceptions, AST parsing syntax warning suppressions, and hallucination catalog data files.
    - `common_hallucinations.json` & `common_hallucinations.py`: Tightened Kubernetes cluster overlay HTTP regex and added catalog entries for `HALLUCINATION-JSON-LOADS-ARBITRARY-CODE-EXECUTION` and `HALLUCINATION-AST-PARSE-SYNTAX-WARNING-SUPPRESSION`.
- [x] **Verification**:
  - Validated 100% pass across all pre-commit hooks (`uv run pre-commit run --all-files`).
  - Validated 100% pass across all 10 CI quality gates (`uv run devops ci`).
