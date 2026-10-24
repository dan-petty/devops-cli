# Tasks

## 1. The rule

- [x] 1.1 Add the violations of `review-cwd-read` to `tests/test_net_construct_rules.py`, one in each package that the rule holds, with the command layer as the tree that it leaves alone, and register the rule in `CONST_AST_GREP_RULE_FILES` (`uv run devops ci test tests/test_net_construct_rules.py tests/test_architectural_invariants.py`).
- [x] 1.2 Add `.ast-grep/rules/review-cwd-read.yml` and its rule tests, and name the working-directory reads in the `constructs` row and in the `ast-grep-scan` hook. On b26caf93 the rule reports 11 reads (`uv run ast-grep test --skip-snapshot-tests`, `uv run ast-grep scan src tests`).

## 2. The scanners take their directories from the caller

- [x] 2.1 Add the failing tests: a Kube-linter finding names the manifest in its own checkout from another directory, and Popeye starts in the directory that its caller gives (`uv run devops ci test tests/test_secops.py`).
- [x] 2.2 Find the Kube-linter tree from the manifest, require `tree` in `run_mypy_scan` and `run_osv_scan` and `workdir` in `run_popeye_scan`, require the root of `relativize_scan_path`, start a scan that is not isolated in the nearest directory of its targets, and give Popeye the directory of `devops k8s audit` (`uv run devops ci test tests/test_secops.py tests/test_osv_scanner.py tests/test_scanner_tool_executor.py tests/test_security_semgrep.py tests/test_review_ruff_mypy_evidence.py tests/test_review_tool_runs.py tests/test_k8s.py`).

## 3. The review takes its workspace from the command

- [x] 3.1 Add the failing tests: from `/`, the feedback export reads no reviews directory outside the workspace, no orchestrator stage takes a `target_dir`, and the aggregation test keeps the Kube-linter finding in the payload of the manifest (`uv run devops ci test tests/test_review_exporter.py tests/ai/review/test_runner.py tests/test_review_security_tools.py`).
- [x] 3.2 Give `export_invalidated_feedback` its `workspace_root`, the review boundary its `working_directory`, and the orchestrator its workspace through the constructor alone. Drop the working directory from the session directory roots, read the summary analysis of the reviewed repository, and read the working directory one time in `devops review path`, `devops review branch`, the PR review helper and `devops review export-feedback` (`uv run devops ci test tests/test_review_runner.py tests/test_review_repos.py tests/test_review_path_routing.py tests/test_review_project_conventions.py tests/test_review_symbol_delta.py tests/test_review_scope.py tests/test_review_stage_flags.py tests/test_review_profile.py tests/test_review_worktree_regression.py tests/ai/review/test_pre_analysis_scope.py tests/test_review_adjudication.py tests/test_review_defenses_and_verification.py tests/test_docs_review_loop.py tests/test_review_untrusted_tree.py`).

## 4. The review tests get the executor fake through the constructor

- [x] 4.1 Answer the canary run of each review tool in `ScannerFake`, as the executor that a test gives and through `scanner_fake`, and run the canary contract case over both (`uv run devops ci test tests/test_scanner_contract.py tests/test_review_canary.py`).
- [x] 4.2 Delete `pin_review_tool_canaries` from the root conftest, and give the fake to the 41 tests that reached a canary through `DirectToolExecutor` (`uv run devops ci test tests/test_review_admission.py tests/test_review_static_analyzers.py tests/test_review_untrusted_tree.py tests/test_security_semgrep.py tests/test_review_pipeline.py tests/test_review_pipeline_go.py tests/test_review_report_integrity.py tests/test_review_path_routing.py tests/ai/review/test_pipeline.py tests/ai/review/test_runner.py tests/test_osv_scanner.py tests/test_review_group_analysis.py tests/test_review_security_tools.py tests/test_scanner_contract.py`).
- [x] 4.3 Run the three named tests over a temporary workspace and fakes, with no patch of a devops-cli name, and measure them (`uv run pytest --durations=0 -n0 tests/test_review_pipeline.py::test_review_pipeline_stages tests/test_review_repos.py::TestReviewReposSubdirectories::test_review_path_summary_in_repos_directory tests/test_review_security_tools.py::test_pipeline_multi_scanner_aggregation`).

## 5. Documentation

- [x] 5.1 Describe the workspace from the caller in ARCHITECTURE.md (section 7.4) and the canary answers of the fake in docs/TESTING.md and in the docstrings of `tests/support/fakes/scanners.py` and `tests/test_scanner_contract.py` (`uv run devops docs check`).
- [x] 5.2 Check the change (`uv run devops openspec check`).

## Workflow follow-up

- The orchestrator takes its enrichers, the threat-intel lookups of Shodan and Cloudflare Radar, through its constructor, with a fake of their HTTP edge and its contract suite once #1381 gives the edge its seam: #1328 already holds this.
- A helper of `core/repo` and a scanner entry point still read the working directory through a default: `get_repo_origin_name()` names the repository of a PR review, and `run_trivy_scan`, `run_kubelinter_scan`, `run_pluto_scan`, `run_bandit_scan` and `run_dive_scan` default to the relative path `.`. The command gives the directory instead: #2127.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
