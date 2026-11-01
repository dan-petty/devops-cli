# Tasks

## 1. AI review runner: remove private imports and patch sites

Reads: none. Changes: `tests/ai/review/test_runner.py`.

- [ ] 1.1 A grep over tests/ai/review/test_runner.py for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches. The file imports only public names and installs fakes through fixtures, and verify that `uv run devops ci test tests/ai/review/test_runner.py` fails on the base
- [ ] 1.2 Remove imports of _check_and_warn_perimeter_changes, _execute_review_workflow, _record_review_metrics, _run_orchestrator_review. Rewrite each test to call the public devops review command via the cli fixture. Replace patch of _load_file_analysis_metas and _print_analysis_metadata with a shared fake installed through a conftest fixture. Replace MagicMock(spec=ReviewLLMClient) with ModelFake from tests.support.fakes.model, and verify that `uv run devops ci test tests/ai/review/test_runner.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. AI review pipeline: remove private imports and patch sites

Reads: none. Changes: `tests/ai/review/test_pipeline.py`.

- [ ] 2.1 A grep over tests/ai/review/test_pipeline.py for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches. The file imports only public names and installs fakes through fixtures, and verify that `uv run devops ci test tests/ai/review/test_pipeline.py` fails on the base
- [ ] 2.2 Remove imports of _admit_scanner_findings and _wrap_static_findings. Rewrite tests to call the public devops review command via the cli fixture. Replace monkeypatch.setattr of _scan_kubernetes_manifests, _scan_container_and_lockfiles, _scan_secrets, _scan_semgrep with ScannerFake installed through the scanner_fake fixture. Replace monkeypatch of run_bandit_scan and run_semgrep_scan with ScannerFake routes, and verify that `uv run devops ci test tests/ai/review/test_pipeline.py` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. AI review cited code and removed options

Reads: none. Changes: `tests/ai/review/test_cited_code.py`, `tests/commands/test_review_removed_options.py`.

- [ ] 3.1 A grep over both files for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/ai/review/test_cited_code.py tests/commands/test_review_removed_options.py` fails on the base
- [ ] 3.2 In test_cited_code.py: replace MagicMock() for llm_client with ModelFake. In test_review_removed_options.py: remove all patch calls of _execute_review_workflow, _prepare_pr_content, _prepare_branch_content, _prepare_path_content, _select_samples. The tests already use CliRunner and only need the patch context managers removed because the removed options exit 2 before any internal function is reached, and verify that `uv run devops ci test tests/ai/review/test_cited_code.py tests/commands/test_review_removed_options.py` passes
- [ ] 3.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 4. AI review pipeline go, group analysis, canary

Reads: none. Changes: `tests/test_review_pipeline_go.py`, `tests/test_review_group_analysis.py`, `tests/test_review_canary.py`.

- [ ] 4.1 A grep over the three files for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/test_review_pipeline_go.py tests/test_review_group_analysis.py tests/test_review_canary.py` fails on the base
- [ ] 4.2 Remove private imports and patch sites. Rewrite tests to call the public devops review command via the cli fixture. Replace MagicMock instances with ModelFake and ScannerFake from tests/support/fakes/. Install fakes through conftest fixtures, and verify that `uv run devops ci test tests/test_review_pipeline_go.py tests/test_review_group_analysis.py tests/test_review_canary.py` passes
- [ ] 4.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 5. AI review rules pack, syntax masking, ruff/mypy evidence

Reads: none. Changes: `tests/test_review_rules_pack.py`, `tests/test_review_syntax_masking.py`, `tests/test_review_ruff_mypy_evidence.py`.

- [ ] 5.1 A grep over the three files for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/test_review_rules_pack.py tests/test_review_syntax_masking.py tests/test_review_ruff_mypy_evidence.py` fails on the base
- [ ] 5.2 Remove private imports and patch sites. Rewrite tests to call the public devops review command via the cli fixture. Replace MagicMock instances with shared fakes from tests/support/fakes/, and verify that `uv run devops ci test tests/test_review_rules_pack.py tests/test_review_syntax_masking.py tests/test_review_ruff_mypy_evidence.py` passes
- [ ] 5.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 6. AI review tool runs and tool sandbox

Reads: none. Changes: `tests/test_review_tool_runs.py`, `tests/test_review_tool_sandbox.py`.

- [ ] 6.1 A grep over both files for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/test_review_tool_runs.py tests/test_review_tool_sandbox.py` fails on the base
- [ ] 6.2 Remove private imports and patch sites. Rewrite tests to call the public devops review command via the cli fixture. Replace MagicMock instances with ScannerFake from tests/support/fakes/scanners.py, and verify that `uv run devops ci test tests/test_review_tool_runs.py tests/test_review_tool_sandbox.py` passes
- [ ] 6.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 7. K8s IPv6/proxy boundaries and volume reclaim

Reads: none. Changes: `tests/test_k8s_ipv6_and_proxy_boundaries.py`, `tests/test_k8s_volume_reclaim.py`.

- [ ] 7.1 A grep over both files for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/test_k8s_ipv6_and_proxy_boundaries.py tests/test_k8s_volume_reclaim.py` fails on the base
- [ ] 7.2 Remove 15 patch sites and 9 private imports in test_k8s_ipv6_and_proxy_boundaries.py. Remove 12 patch sites in test_k8s_volume_reclaim.py. Rewrite tests to call the public devops k8s command via the cli fixture. Replace MagicMock instances with FakeCoreV1 and client from tests/k8s_fakes.py, and verify that `uv run devops ci test tests/test_k8s_ipv6_and_proxy_boundaries.py tests/test_k8s_volume_reclaim.py` passes
- [ ] 7.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 8. K8s GPU placement and tempo

Reads: none. Changes: `tests/test_k8s_gpu_placement.py`, `tests/test_k8s_tempo.py`.

- [ ] 8.1 A grep over both files for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/test_k8s_gpu_placement.py tests/test_k8s_tempo.py` fails on the base
- [ ] 8.2 Remove 11 patch sites in test_k8s_gpu_placement.py. Remove 4 patch sites and 1 private import in test_k8s_tempo.py. Rewrite tests to call the public devops k8s command via the cli fixture. Replace MagicMock instances with FakeCoreV1 from tests/k8s_fakes.py, and verify that `uv run devops ci test tests/test_k8s_gpu_placement.py tests/test_k8s_tempo.py` passes
- [ ] 8.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 9. K8s agents manifests and monitoring alerting

Reads: none. Changes: `tests/test_k8s_agents_manifests.py`, `tests/test_k8s_monitoring_alerting.py`.

- [ ] 9.1 A grep over both files for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/test_k8s_agents_manifests.py tests/test_k8s_monitoring_alerting.py` fails on the base
- [ ] 9.2 Remove 1 private import in each file. Rewrite tests to call the public devops k8s command via the cli fixture. Replace MagicMock instances with FakeCoreV1 from tests/k8s_fakes.py, and verify that `uv run devops ci test tests/test_k8s_agents_manifests.py tests/test_k8s_monitoring_alerting.py` passes
- [ ] 9.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 10. Telemetry LLM content and RAG KB sync

Reads: none. Changes: `tests/test_telemetry_llm_content.py`, `tests/test_rag_kb_sync.py`.

- [ ] 10.1 A grep over both files for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/test_telemetry_llm_content.py tests/test_rag_kb_sync.py` fails on the base
- [ ] 10.2 Remove 9 patch sites in test_telemetry_llm_content.py. Remove 8 patch sites in test_rag_kb_sync.py. Rewrite tests to call the public devops command via the cli fixture. Replace MagicMock instances with shared fakes from tests/support/fakes/, and verify that `uv run devops ci test tests/test_telemetry_llm_content.py tests/test_rag_kb_sync.py` passes
- [ ] 10.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 11. Security zizmor, OSV scanner, golangci-lint scanner

Reads: none. Changes: `tests/test_security_zizmor.py`, `tests/test_osv_scanner.py`, `tests/test_golangci_lint_scanner.py`.

- [ ] 11.1 A grep over the three files for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/test_security_zizmor.py tests/test_osv_scanner.py tests/test_golangci_lint_scanner.py` fails on the base
- [ ] 11.2 Remove 6 patch sites in test_security_zizmor.py. Remove 2 patch sites and 2 private imports in test_osv_scanner.py. Remove 3 patch sites in test_golangci_lint_scanner.py. Rewrite tests to call the public devops security command via the cli fixture. Replace MagicMock instances with ScannerFake from tests/support/fakes/scanners.py, and verify that `uv run devops ci test tests/test_security_zizmor.py tests/test_osv_scanner.py tests/test_golangci_lint_scanner.py` passes
- [ ] 11.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 12. CI repeat, CI mutate, cache fuzzing

Reads: none. Changes: `tests/test_ci_repeat.py`, `tests/test_ci_mutate.py`, `tests/ci/test_cache_fuzzing.py`.

- [ ] 12.1 A grep over the three files for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/test_ci_repeat.py tests/test_ci_mutate.py tests/ci/test_cache_fuzzing.py` fails on the base
- [ ] 12.2 Remove 3 patch sites in test_ci_repeat.py. Remove 1 patch site in test_ci_mutate.py. In test_cache_fuzzing.py: remove import of _worktree_divergent_paths and patch of _get_git_output. Rewrite the fuzzing test to call the public devops ci command via the cli fixture, or make _worktree_divergent_paths public if it is a genuine product function. Replace patch of _get_git_output with ProcessFake from tests/support/fakes/process.py, and verify that `uv run devops ci test tests/test_ci_repeat.py tests/test_ci_mutate.py tests/ci/test_cache_fuzzing.py` passes
- [ ] 12.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 13. Core cleanup fuzzing, clock contract, core repo

Reads: none. Changes: `tests/core/test_cleanup_fuzzing.py`, `tests/core/test_clock_contract.py`, `tests/test_core_repo.py`.

- [ ] 13.1 A grep over the three files for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/core/test_cleanup_fuzzing.py tests/core/test_clock_contract.py tests/test_core_repo.py` fails on the base
- [ ] 13.2 In test_cleanup_fuzzing.py: remove import of _listed_worktrees and patch of run_subprocess. Rewrite to call the public devops command via the cli fixture, or make _listed_worktrees public. Replace patch with ProcessFake. In test_clock_contract.py: remove 1 patch site. In test_core_repo.py: remove 1 patch site. Replace MagicMock instances with shared fakes, and verify that `uv run devops ci test tests/core/test_cleanup_fuzzing.py tests/core/test_clock_contract.py tests/test_core_repo.py` passes
- [ ] 13.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 14. Commands test_pr: remove set_delivered_status patch

Reads: none. Changes: `tests/commands/test_pr.py`.

- [ ] 14.1 A grep over tests/commands/test_pr.py for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/commands/test_pr.py` fails on the base
- [ ] 14.2 Remove the 2 private imports. The no_status_write fixture uses monkeypatch.setattr of set_delivered_status with raising=False. Replace with a shared fake or remove if the function is no longer called in the test path. The file already uses GitHubApiFake, ProcessFake, and ClockFake, so only the set_delivered_status patch needs removal, and verify that `uv run devops ci test tests/commands/test_pr.py` passes
- [ ] 14.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 15. AI research: socratic, mental model, analogies, forage

Reads: none. Changes: `tests/test_ai_research_socratic.py`, `tests/test_ai_research_mental_model.py`, `tests/test_ai_research_analogies.py`, `tests/test_ai_research_forage.py`.

- [ ] 15.1 A grep over the four files for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/test_ai_research_socratic.py tests/test_ai_research_mental_model.py tests/test_ai_research_analogies.py tests/test_ai_research_forage.py` fails on the base
- [ ] 15.2 Remove 6 patch sites and 2 private imports in test_ai_research_socratic.py. Remove 4 patch sites in test_ai_research_mental_model.py. Remove 2 patch sites in test_ai_research_analogies.py. Remove 1 private import in test_ai_research_forage.py. Rewrite tests to call the public devops ai command via the cli fixture. Replace MagicMock instances with ModelFake from tests/support/fakes/model.py, and verify that `uv run devops ci test tests/test_ai_research_socratic.py tests/test_ai_research_mental_model.py tests/test_ai_research_analogies.py tests/test_ai_research_forage.py` passes
- [ ] 15.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 16. LLM stream fakes: remove private method patches

Reads: none. Changes: `tests/llm_stream_fakes.py`.

- [ ] 16.1 A grep over tests/llm_stream_fakes.py for 'patch("devops_cli' and 'monkeypatch.setattr' targeting private names returns zero matches, and verify that `uv run devops ci test tests/llm_stream_fakes.py` fails on the base
- [ ] 16.2 Remove 4 patch sites: _shared_client, _create_http_client, _query_model_info, _max_attempts. Replace monkeypatch.setattr of LLMClient._shared_client and LLMClient._create_http_client with a public seam or a shared fake transport. Replace patch of _query_model_info with a fixture. Replace patch of _max_attempts with a constructor parameter or public property, and verify that `uv run devops ci test tests/llm_stream_fakes.py` passes
- [ ] 16.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 17. Argo gitops fuzzing: remove private import

Reads: none. Changes: `tests/argo/test_gitops_fuzzing.py`.

- [ ] 17.1 A grep over tests/argo/test_gitops_fuzzing.py for 'from devops_cli.* import _' returns zero matches, and verify that `uv run devops ci test tests/argo/test_gitops_fuzzing.py` fails on the base
- [ ] 17.2 Remove import of _parse_drift_event. Rewrite the fuzzing test to call the public devops argo command via the cli fixture, or make _parse_drift_event public if it is a genuine product function, and verify that `uv run devops ci test tests/argo/test_gitops_fuzzing.py` passes
- [ ] 17.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 18. Fail to pass, config field validation, PR hardening report

Reads: none. Changes: `tests/test_fail_to_pass.py`, `tests/test_config_field_validation.py`, `tests/test_pr_hardening_report.py`.

- [ ] 18.1 A grep over the three files for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/test_fail_to_pass.py tests/test_config_field_validation.py tests/test_pr_hardening_report.py` fails on the base
- [ ] 18.2 Remove 4 patch sites in test_fail_to_pass.py. Remove 1 patch site and 2 private imports in test_config_field_validation.py. Remove 7 patch sites in test_pr_hardening_report.py. Rewrite tests to call the public devops command via the cli fixture. Replace MagicMock instances with shared fakes from tests/support/fakes/, and verify that `uv run devops ci test tests/test_fail_to_pass.py tests/test_config_field_validation.py tests/test_pr_hardening_report.py` passes
- [ ] 18.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 19. Architectural invariants, roadmap return, URL credential masking

Reads: none. Changes: `tests/test_architectural_invariants.py`, `tests/test_roadmap_return.py`, `tests/test_url_credential_masking.py`.

- [ ] 19.1 A grep over the three files for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/test_architectural_invariants.py tests/test_roadmap_return.py tests/test_url_credential_masking.py` fails on the base
- [ ] 19.2 Remove 2 private imports in test_architectural_invariants.py. Remove 2 patch sites in test_roadmap_return.py. Remove 2 patch sites in test_url_credential_masking.py. Rewrite tests to call the public devops command via the cli fixture. Replace MagicMock instances with shared fakes, and verify that `uv run devops ci test tests/test_architectural_invariants.py tests/test_roadmap_return.py tests/test_url_credential_masking.py` passes
- [ ] 19.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 20. All commands help dryrun, CLI format adoption, CLI startup imports

Reads: none. Changes: `tests/test_all_commands_help_dryrun.py`, `tests/test_cli_format_adoption.py`, `tests/test_cli_startup_imports.py`.

- [ ] 20.1 A grep over the three files for 'from devops_cli.* import _' returns zero matches, and verify that `uv run devops ci test tests/test_all_commands_help_dryrun.py tests/test_cli_format_adoption.py tests/test_cli_startup_imports.py` fails on the base
- [ ] 20.2 Remove 1 private import in each file. Rewrite tests to call the public devops command via the cli fixture. Replace MagicMock instances with shared fakes from tests/support/fakes/, and verify that `uv run devops ci test tests/test_all_commands_help_dryrun.py tests/test_cli_format_adoption.py tests/test_cli_startup_imports.py` passes
- [ ] 20.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 21. Codebase hygiene, KB manuals metadata, stack dashboards, survey cmd

Reads: none. Changes: `tests/test_codebase_hygiene_and_shims.py`, `tests/test_kb_manuals_metadata.py`, `tests/test_stack_dashboards.py`, `tests/test_survey_cmd.py`.

- [ ] 21.1 A grep over the four files for 'from devops_cli.* import _' and 'patch("devops_cli' returns zero matches, and verify that `uv run devops ci test tests/test_codebase_hygiene_and_shims.py tests/test_kb_manuals_metadata.py tests/test_stack_dashboards.py tests/test_survey_cmd.py` fails on the base
- [ ] 21.2 Remove 1 private import in test_codebase_hygiene_and_shims.py. Remove 1 private import in test_kb_manuals_metadata.py. Remove 1 private import in test_stack_dashboards.py. Remove 1 patch site in test_survey_cmd.py. Rewrite tests to call the public devops command via the cli fixture. Replace MagicMock instances with shared fakes, and verify that `uv run devops ci test tests/test_codebase_hygiene_and_shims.py tests/test_kb_manuals_metadata.py tests/test_stack_dashboards.py tests/test_survey_cmd.py` passes
- [ ] 21.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
