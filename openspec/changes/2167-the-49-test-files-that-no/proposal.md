# Proposal

## Why

#2167: 49 test files added after the 2026-10-07 census patch devops_cli internal names or import private names. No child of #1307 owns them. They must test through public interfaces over shared fakes, as ADR 0007 and docs/TESTING.md require.

## What Changes

- Rewrite 49 test files to call public CLI commands and install shared fakes through fixtures instead of patching devops_cli private names
- Remove private product code that exists only to be patched by a test, per #1307 Q27
- Replace MagicMock instances with shared fakes from tests/support/fakes/
- Add a spec requirement that tests in the 49-file set use public interfaces and shared fakes
- The change fits one pull request.

## Capabilities

### New Capabilities

- `test-public-interface`: tests-use-public-interfaces

### Modified Capabilities

None.

## Impact

- Tests: `tests/ai/review/test_runner.py`, `tests/ai/review/test_pipeline.py`, `tests/ai/review/test_cited_code.py`, `tests/commands/test_review_removed_options.py`, `tests/test_review_pipeline_go.py`, `tests/test_review_group_analysis.py`, `tests/test_review_canary.py`, `tests/test_review_rules_pack.py`, `tests/test_review_syntax_masking.py`, `tests/test_review_ruff_mypy_evidence.py`, `tests/test_review_tool_runs.py`, `tests/test_review_tool_sandbox.py`, `tests/test_k8s_ipv6_and_proxy_boundaries.py`, `tests/test_k8s_volume_reclaim.py`, `tests/test_k8s_gpu_placement.py`, `tests/test_k8s_tempo.py`, `tests/test_k8s_agents_manifests.py`, `tests/test_k8s_monitoring_alerting.py`, `tests/test_telemetry_llm_content.py`, `tests/test_rag_kb_sync.py`, `tests/test_security_zizmor.py`, `tests/test_osv_scanner.py`, `tests/test_golangci_lint_scanner.py`, `tests/test_ci_repeat.py`, `tests/test_ci_mutate.py`, `tests/ci/test_cache_fuzzing.py`, `tests/core/test_cleanup_fuzzing.py`, `tests/core/test_clock_contract.py`, `tests/test_core_repo.py`, `tests/commands/test_pr.py`, `tests/test_ai_research_socratic.py`, `tests/test_ai_research_mental_model.py`, `tests/test_ai_research_analogies.py`, `tests/test_ai_research_forage.py`, `tests/llm_stream_fakes.py`, `tests/argo/test_gitops_fuzzing.py`, `tests/test_fail_to_pass.py`, `tests/test_config_field_validation.py`, `tests/test_pr_hardening_report.py`, `tests/test_architectural_invariants.py`, `tests/test_roadmap_return.py`, `tests/test_url_credential_masking.py`, `tests/test_all_commands_help_dryrun.py`, `tests/test_cli_format_adoption.py`, `tests/test_cli_startup_imports.py`, `tests/test_codebase_hygiene_and_shims.py`, `tests/test_kb_manuals_metadata.py`, `tests/test_stack_dashboards.py`, `tests/test_survey_cmd.py`

## Feasibility

- The context shows tests/ai/review/test_runner.py importing _check_and_warn_perimeter_changes, _execute_review_workflow, _record_review_metrics, _run_orchestrator_review and patching _load_file_analysis_metas and _print_analysis_metadata, confirming the private-import and patch pattern.
- The context shows tests/ci/test_cache_fuzzing.py importing _worktree_divergent_paths and patching _get_git_output, confirming the pattern in the CI domain.
- The context shows tests/llm_stream_fakes.py patching _shared_client, _create_http_client, _query_model_info and _max_attempts, confirming the pattern in the LLM client domain.
- The context shows tests/commands/test_pr.py using shared fakes (GitHubApiFake, ProcessFake, ClockFake) and a cli fixture, confirming the target pattern already exists in the repository.
- First checks the implementation runs: (1) grep -rn 'from devops_cli.* import _' tests/ to enumerate all private imports; (2) grep -rn 'patch("devops_cli' tests/ to enumerate all patch sites; (3) uv run devops ci test tests/ to confirm the baseline passes before changes.

## Existing Tool Considered

No external tool covers this need. The repository already provides shared fakes in tests/support/fakes/ (GitFake, ProcessFake, ClockFake, GitHubApiFake, ModelFake, ScannerFake) and a cli fixture for CLI-level testing. The change reuses these internal fakes and the existing CliRunner pattern seen in tests/commands/test_pr.py. The change deletes private product code that existed only for test patches, such as the functions targeted by the 146 patch sites across 33 files.
