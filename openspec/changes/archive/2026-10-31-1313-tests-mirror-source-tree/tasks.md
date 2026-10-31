# Tasks
## 1. Conftest Split
- [x] 1.1 Move non-floor shared fixtures (cli, config, model_fake, process_fake, docker_engine, valkey, qdrant, embedder, git, spend_ledger, tracer, review_sessions, roadmap, web) from root tests/conftest.py to tests/support/ modules.
- [x] 1.2 Verify tests/conftest.py contains only hermetic floor fixtures, environment resets, network block, and bootstrap plugin registration.

## 2. Directory Mirror Move
- [x] 2.1 Move each test file from tests/ to its mirror package directory or tests/invariants/ with git mv.
- [x] 2.2 Ensure every test directory has an empty __init__.py.

## 3. Layout Ratchet and Pre-commit
- [x] 3.1 Add layout ratchet in tests/invariants/test_source_tree.py checking test locations against mirror packages and ceiling 0.
- [x] 3.2 Add tests for layout ratchet with fixture trees (disallowed directory, tests/support test, and deleted mirror package).
- [x] 3.3 Update .pre-commit-config.yaml detect-private-key exclusions to new test file paths.

## 4. Verification
- [x] 4.1 Verify git diff --name-status -M100% shows R100 for all moved test files.
- [x] 4.2 Verify normalized test collection IDs match base.
- [x] 4.3 Run uv run devops ci and pass all checks.

## Fixture Destinations
| Fixture | Destination | Rationale |
|---|---|---|
| `cli` | `tests/support/cli.py` | Shared command runner fixture (#1310) |
| `config`, `_deep_merge_config` | `tests/support/config.py` | Shared config override fixture (#1310) |
| `model_fake` | `tests/support/fakes/model.py` | Sits beside ModelFake definition |
| `process_fake` | `tests/support/fakes/process.py` | Sits beside ProcessFake definition |
| `docker_engine`, `docker_client`, `docker_endpoint_env` | `tests/support/fakes/docker_engine.py` | Sits beside DockerEngineFake definition |
| `valkey` | `tests/support/fakes/valkey.py` | Sits beside ValkeyFake definition |
| `qdrant` | `tests/support/fakes/qdrant.py` | Sits beside FakeQdrantClient definition |
| `embedder` | `tests/support/fakes/embeddings.py` | Sits beside FakeEmbedder definition |
| `public_dns`, `stub_web` | `tests/support/web.py` | Web and DNS fakes used across packages |
| `known_hosts`, `git`, `nested_worktree`, `symbol_removal_repo` | `tests/support/git_scenarios.py` | Git fixtures used across packages |
| `spend_ledger` | `tests/support/spend.py` | Spend ledger fixture used across packages |
| `tracer` | `tests/support/tracer.py` | Telemetry tracer fixture used across packages |
| `review_store`, `write_review_session`, `review_history` | `tests/support/review_sessions.py` | Review session fixtures used across packages |
| `github_roadmap_factory`, `roadmap_store_repos`, `roadmap_store`, `unreadable_github_roadmap` | `tests/support/roadmap.py` | Roadmap fixtures used across packages |

## Move Regeneration Command
To regenerate the moves:
```bash
python3 -c '
import json, subprocess, os
with open(".data/agent/scratch/final_mapping.json") as f:
    m = json.load(f)
for fn, d in m.items():
    dest = d["dest"]
    os.makedirs(f"tests/{dest}", exist_ok=True)
    subprocess.run(["git", "mv", f"tests/{fn}", f"tests/{dest}/{fn}"], check=True)
'
```

## Move Table
| Old Path | New Directory | Ownership % | Runner-up | Rationale |
|---|---|---|---|---|
| `tests/test_agent.py` | `tests/ai/agents` | 46.2% | ai/tools (3) | 46.2% references (6/13) |
| `tests/test_agent_invariants.py` | `tests/ai/agents` | 100.0% | - | Explicit assignment in #1313 / Phase E |
| `tests/test_agent_memory.py` | `tests/ai/agents` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_agents_md_claims.py` | `tests/invariants` | 100.0% | - | Invariant test of committed repo files |
| `tests/test_ai_agent_capabilities.py` | `tests/ai/agents` | 94.4% | ai/spend (1) | 94.4% references (17/18) |
| `tests/test_ai_agent_deferred_tools.py` | `tests/ai/agents` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_ai_analyze_outlines.py` | `tests/ai/analyze` | 70.0% | ai/rag (2) | 70.0% references (7/10) |
| `tests/test_ai_ast_cli.py` | `tests/ai/ast` | 50.0% | commands (1) | 50.0% references (1/2) |
| `tests/test_ai_benchmark.py` | `tests/ai/benchmark` | 56.2% | commands (3) | 56.2% references (9/16) |
| `tests/test_ai_benchmark_mcp_tool.py` | `tests/ai/mcp` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_ai_capability.py` | `tests/ai` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ai_chaos_model.py` | `tests/telemetry` | 33.3% | ai/mcp (2) | 33.3% references (2/6) |
| `tests/test_ai_chat_reply_stream.py` | `tests/ai/client` | 66.7% | ai/spend (1) | 66.7% references (2/3) |
| `tests/test_ai_client_credentials.py` | `tests/ai/client` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ai_client_error_reason.py` | `tests/ai/client` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ai_client_factory.py` | `tests/ai/client` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ai_client_finish_reasons.py` | `tests/ai/client` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ai_client_network.py` | `tests/ai/client` | 100.0% | - | 100.0% references (4/4) |
| `tests/test_ai_client_providers_and_embeddings.py` | `tests/ai/client` | 50.0% | ai/benchmark (3) | 50.0% references (4/8) |
| `tests/test_ai_client_retries.py` | `tests/ai/client` | 50.0% | http (1) | 50.0% references (1/2) |
| `tests/test_ai_client_security.py` | `tests/ai/client` | 50.0% | ai/models (1) | 50.0% references (1/2) |
| `tests/test_ai_client_structured.py` | `tests/ai/client` | 33.3% | ai (3) | 33.3% references (3/9) |
| `tests/test_ai_client_style_request.py` | `tests/ai` | 50.0% | ai/client (1) | 50.0% references (2/4) |
| `tests/test_ai_client_telemetry.py` | `tests/ai/client` | 55.6% | telemetry (3) | 55.6% references (5/9) |
| `tests/test_ai_cmd.py` | `tests/commands` | 100.0% | ai/agents (14) | 100.0% references (19/47) |
| `tests/test_ai_controller.py` | `tests/ai/controller` | 100.0% | - | 100.0% references (5/5) |
| `tests/test_ai_diagram.py` | `tests/ai` | 50.0% | commands (1) | 50.0% references (1/2) |
| `tests/test_ai_explain.py` | `tests/ai` | 50.0% | commands (1) | 50.0% references (1/2) |
| `tests/test_ai_fixer.py` | `tests/ai` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_ai_gateway.py` | `tests/ai/mcp` | 45.5% | ai/client (3) | 45.5% references (5/11) |
| `tests/test_ai_gateway_base_url.py` | `tests/ai/client` | 50.0% | ai (1) | 50.0% references (1/2) |
| `tests/test_ai_gateway_portkey.py` | `tests/ai` | 50.0% | commands (1) | 50.0% references (1/2) |
| `tests/test_ai_gateway_probes.py` | `tests/ai` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ai_gateway_render.py` | `tests/ai` | 50.0% | commands (1) | 50.0% references (1/2) |
| `tests/test_ai_gateway_tune.py` | `tests/ai` | 60.0% | ai/spend (1) | 60.0% references (3/5) |
| `tests/test_ai_init.py` | `tests/ai/analyze` | 80.0% | ai (1) | 80.0% references (4/5) |
| `tests/test_ai_inspection.py` | `tests/ai` | 66.7% | ai/analyze (1) | 66.7% references (2/3) |
| `tests/test_ai_model_sampling.py` | `tests/ai` | 60.0% | ai/client (1) | 60.0% references (3/5) |
| `tests/test_ai_prewarm.py` | `tests/ai/mcp` | 41.7% | commands (4) | 41.7% references (5/12) |
| `tests/test_ai_prompt_eval.py` | `tests/ai` | 66.7% | commands (1) | 66.7% references (2/3) |
| `tests/test_ai_repomap.py` | `tests/ai` | 50.0% | commands (1) | 50.0% references (1/2) |
| `tests/test_ai_request_priority.py` | `tests/ai/client` | 80.0% | telemetry (1) | 80.0% references (4/5) |
| `tests/test_ai_research_analogies.py` | `tests/ai/research` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_ai_research_forage.py` | `tests/ai/research` | 75.0% | commands (1) | 75.0% references (3/4) |
| `tests/test_ai_research_marginalia.py` | `tests/ai/research` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_ai_research_mental_model.py` | `tests/ai/research` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_ai_research_socratic.py` | `tests/ai/research` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_ai_review_pool.py` | `tests/ai/review` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ai_served_by.py` | `tests/ai/client` | 33.3% | ai/spend (1) | 33.3% references (1/3) |
| `tests/test_ai_spec.py` | `tests/ai/spec` | 50.0% | commands (1) | 50.0% references (1/2) |
| `tests/test_ai_spend_cli.py` | `tests/ai/spend` | 50.0% | commands (2) | 50.0% references (3/6) |
| `tests/test_ai_spend_dispatch.py` | `tests/ai/spend` | 60.0% | ai (1) | 60.0% references (3/5) |
| `tests/test_ai_spend_ledger.py` | `tests/ai/spend` | 55.6% | commands (3) | 55.6% references (5/9) |
| `tests/test_ai_spend_payoff.py` | `tests/ai/spend` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ai_spend_pricing.py` | `tests/ai/spend` | 100.0% | - | 100.0% references (8/8) |
| `tests/test_ai_spend_prometheus.py` | `tests/ai/spend` | 40.0% | commands (1) | 40.0% references (2/5) |
| `tests/test_ai_streaming.py` | `tests/ai/client` | 62.5% | ai (2) | 62.5% references (5/8) |
| `tests/test_ai_subcommands_rag.py` | `tests/ai/rag` | 75.0% | commands (1) | 75.0% references (3/4) |
| `tests/test_ai_task_implement.py` | `tests/ai/client` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ai_task_loader.py` | `tests/ai` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ai_task_metadata.py` | `tests/git` | 44.4% | commands (3) | 44.4% references (4/9) |
| `tests/test_ai_task_settings_paths.py` | `tests/config` | 50.0% | exceptions (1) | 50.0% references (1/2) |
| `tests/test_ai_test_gen.py` | `tests/ai/mcp` | 33.3% | ai (1) | 33.3% references (1/3) |
| `tests/test_aibom.py` | `tests/security` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_all_commands_help_dryrun.py` | `tests/commands` | 90.9% | commands/k8s (1) | 90.9% references (10/11) |
| `tests/test_analyze.py` | `tests/commands` | 42.9% | ai/analyze (15) | 42.9% references (18/42) |
| `tests/test_architectural_invariants.py` | `tests/invariants` | 100.0% | - | Invariant test of committed repo files |
| `tests/test_argo.py` | `tests/commands` | 66.7% | k8s (2) | 66.7% references (8/12) |
| `tests/test_argo_crd.py` | `tests/argo` | 50.0% | k8s (1) | 50.0% references (1/2) |
| `tests/test_argo_fleet.py` | `tests/argo` | 80.4% | ai/mcp (8) | 80.4% references (45/56) |
| `tests/test_argo_gitops.py` | `tests/argo` | 95.8% | commands (1) | 95.8% references (23/24) |
| `tests/test_argo_helm_records.py` | `tests/argo` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ast_more_languages.py` | `tests/ai/ast` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_audit_logger.py` | `tests/core` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_audit_stream.py` | `tests/core` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_batch_2_review_defects.py` | `tests/ai/client` | 22.2% | ai (2) | 22.2% references (2/9) |
| `tests/test_branch_form.py` | `tests/git` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_branches.py` | `tests/commands` | 100.0% | - | 100.0% references (7/7) |
| `tests/test_builtin_tools.py` | `tests/security` | 42.1% | ai/rag (5) | 42.1% references (8/19) |
| `tests/test_category_metrics.py` | `tests/ai/review` | 60.0% | ai/personas (1) | 60.0% references (3/5) |
| `tests/test_change_folders.py` | `tests/invariants` | 100.0% | - | Invariant test of committed repo files |
| `tests/test_ci.py` | `tests/commands` | 76.3% | core (7) | 76.3% references (45/59) |
| `tests/test_ci_build_index.py` | `tests/commands` | 50.0% | ci (1) | 50.0% references (2/4) |
| `tests/test_ci_cache.py` | `tests/ci` | 60.0% | commands (2) | 60.0% references (3/5) |
| `tests/test_ci_cache_fingerprint.py` | `tests/ci` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ci_diagnostics.py` | `tests/ci` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ci_dry_run.py` | `tests/commands` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ci_gate_admission.py` | `tests/ci` | 33.3% | core (2) | 33.3% references (2/6) |
| `tests/test_ci_gate_slots.py` | `tests/ci` | 50.0% | core (1) | 50.0% references (1/2) |
| `tests/test_ci_job_time.py` | `tests/github` | 66.7% | ci (1) | 66.7% references (2/3) |
| `tests/test_ci_maintain.py` | `tests/commands` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ci_mutate.py` | `tests/ci` | 50.0% | commands (1) | 50.0% references (1/2) |
| `tests/test_ci_repeat.py` | `tests/commands` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_claude_provider.py` | `tests/ai/client` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_cli_format_adoption.py` | `tests/commands` | 100.0% | - | CLI command format checks across all commands |
| `tests/test_cli_startup_imports.py` | `tests/commands` | 100.0% | - | CLI startup import bounds across commands |
| `tests/test_cloudflare_commands.py` | `tests/commands` | 94.9% | cloudflare (2) | 94.9% references (37/39) |
| `tests/test_code_metrics.py` | `tests/core` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_codebase_hygiene_and_shims.py` | `tests/ai/rag` | 80.0% | security (1) | 80.0% references (4/5) |
| `tests/test_command_builders.py` | `tests/config` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_common_tools.py` | `tests/ai` | 50.0% | telemetry (1) | 50.0% references (1/2) |
| `tests/test_config_audit_keys.py` | `tests/commands` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_config_cmd.py` | `tests/commands` | 100.0% | core (1) | 100.0% references (2/3) |
| `tests/test_config_commands.py` | `tests/commands` | 82.6% | github (2) | 82.6% references (19/23) |
| `tests/test_config_declarations.py` | `tests/security` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_config_env_overrides.py` | `tests/telemetry` | 50.0% | ai (1) | 50.0% references (3/6) |
| `tests/test_config_field_validation.py` | `tests/commands` | 50.0% | telemetry (1) | 50.0% references (1/2) |
| `tests/test_config_save_round_trip.py` | `tests/config` | 50.0% | exceptions (1) | 50.0% references (1/2) |
| `tests/test_config_settings_cache.py` | `tests/core` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_config_write_history.py` | `tests/config` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_consolidation_binaries.py` | `tests/core` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_consolidation_core_paths.py` | `tests/core` | 100.0% | - | 100.0% references (4/4) |
| `tests/test_consolidation_dry_run_decorator.py` | `tests/dry_run` | 100.0% | - | 100.0% references (7/7) |
| `tests/test_consolidation_process_json.py` | `tests/core` | 100.0% | - | 100.0% references (7/7) |
| `tests/test_consolidation_serialization.py` | `tests/telemetry` | 50.0% | core (1) | 50.0% references (3/6) |
| `tests/test_consolidation_table_builder.py` | `tests/output` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_context_budget.py` | `tests/ai` | 50.0% | commands (1) | 50.0% references (1/2) |
| `tests/test_context_packer.py` | `tests/ai` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_contract_injection.py` | `tests/ai/review` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_core_repo.py` | `tests/core` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_coverage_index.py` | `tests/core` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_crypto_tls.py` | `tests/crypto` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_custom_personas.py` | `tests/ai/personas` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_data_dir_configuration.py` | `tests/ai/benchmark` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_data_dir_worktrees.py` | `tests/core` | 16.7% | ai (2) | 16.7% references (3/18) |
| `tests/test_defect_classifier.py` | `tests/github` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_dependency_audit.py` | `tests/commands` | 50.0% | core (1) | 50.0% references (1/2) |
| `tests/test_dependency_remediator.py` | `tests/security` | 88.9% | ai (1) | 88.9% references (8/9) |
| `tests/test_devcontainer.py` | `tests/commands` | 70.4% | core (11) | 70.4% references (38/54) |
| `tests/test_difftastic.py` | `tests/ai/diff` | 100.0% | - | 100.0% references (7/7) |
| `tests/test_docker.py` | `tests/commands` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_docker_cosign.py` | `tests/ai/mcp` | 66.7% | commands (1) | 66.7% references (2/3) |
| `tests/test_docker_engine.py` | `tests/core` | 66.7% | commands (1) | 66.7% references (2/3) |
| `tests/test_docs.py` | `tests/docs` | 44.4% | commands (3) | 44.4% references (4/9) |
| `tests/test_docs_command_resolver.py` | `tests/core` | 66.7% | k8s (1) | 66.7% references (2/3) |
| `tests/test_docs_ingester.py` | `tests/ai/library` | 33.3% | commands (1) | 33.3% references (1/3) |
| `tests/test_docs_inventory.py` | `tests/docs` | 50.0% | ai (1) | 50.0% references (2/4) |
| `tests/test_docs_knowledge_base_argv.py` | `tests/docs` | 71.4% | commands (1) | 71.4% references (5/7) |
| `tests/test_docs_review_loop.py` | `tests/ai/review` | 33.3% | core (1) | 33.3% references (1/3) |
| `tests/test_docs_routine_tasks.py` | `tests/core` | 100.0% | - | No devops_cli references; placed by domain |
| `tests/test_docs_source_argv_collector.py` | `tests/docs` | 50.0% | ai/mcp (2) | 50.0% references (4/8) |
| `tests/test_embedding_benchmark.py` | `tests/ai/benchmark` | 58.6% | ai/rag (6) | 58.6% references (17/29) |
| `tests/test_embedding_benchmark_failure.py` | `tests/ai/benchmark` | 50.0% | commands (2) | 50.0% references (2/4) |
| `tests/test_embedding_config_retention.py` | `tests/ai/agents` | 50.0% | ai/rag (1) | 50.0% references (1/2) |
| `tests/test_exceptions.py` | `tests/docs` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_executable_criteria.py` | `tests/ai/review` | 50.0% | ai (1) | 50.0% references (1/2) |
| `tests/test_fail_to_pass.py` | `tests/ci` | 50.0% | ai (1) | 50.0% references (2/4) |
| `tests/test_fast_dispatch.py` | `tests/dry_run` | 100.0% | - | 100.0% references (6/6) |
| `tests/test_fastmcp_contracts.py` | `tests/ai/mcp` | 98.6% | docs (1) | 98.6% references (69/70) |
| `tests/test_fastmcp_in_process.py` | `tests/ai/mcp` | 100.0% | - | 100.0% references (4/4) |
| `tests/test_finding_repetition_compression.py` | `tests/ai` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_gateway_review_stall.py` | `tests/http` | 26.7% | ai/retries (3) | 26.7% references (4/15) |
| `tests/test_gh_cmd.py` | `tests/commands` | 100.0% | commands (29) | 100.0% references (31/71) |
| `tests/test_gh_dash_config.py` | `tests/core` | 50.0% | tools_lock (1) | 50.0% references (1/2) |
| `tests/test_gh_issues_milestones.py` | `tests/github` | 36.4% | commands (3) | 36.4% references (4/11) |
| `tests/test_gh_project_workflows.py` | `tests/github` | 68.0% | commands (8) | 68.0% references (17/25) |
| `tests/test_git_commit_snapshot.py` | `tests/git` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_git_contract.py` | `tests/core` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_git_operations.py` | `tests/git` | 100.0% | - | 100.0% references (4/4) |
| `tests/test_git_recording.py` | `tests/core` | 100.0% | - | No devops_cli references; placed by domain |
| `tests/test_git_worktree.py` | `tests/git` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_gitea_doctor.py` | `tests/k8s` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_github_api_metrics.py` | `tests/github` | 75.0% | telemetry (1) | 75.0% references (3/4) |
| `tests/test_github_app_identity.py` | `tests/github` | 66.7% | core (1) | 66.7% references (2/3) |
| `tests/test_github_branch_protection.py` | `tests/github` | 72.0% | commands (7) | 72.0% references (18/25) |
| `tests/test_github_client.py` | `tests/github` | 90.9% | core (1) | 90.9% references (10/11) |
| `tests/test_github_contract.py` | `tests/github` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_github_errors.py` | `tests/github` | 100.0% | - | 100.0% references (10/10) |
| `tests/test_github_issues.py` | `tests/github` | 66.7% | roadmap (2) | 66.7% references (6/9) |
| `tests/test_github_labels.py` | `tests/github` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_github_metrics.py` | `tests/github` | 40.0% | commands (1) | 40.0% references (2/5) |
| `tests/test_github_milestones.py` | `tests/commands` | 66.7% | roadmap (3) | 66.7% references (10/15) |
| `tests/test_github_pages.py` | `tests/github` | 100.0% | - | 100.0% references (5/5) |
| `tests/test_github_pr_monitor.py` | `tests/github` | 100.0% | - | 100.0% references (21/21) |
| `tests/test_github_pr_threads.py` | `tests/github` | 100.0% | - | 100.0% references (33/33) |
| `tests/test_github_project_read.py` | `tests/github` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_github_projects.py` | `tests/github` | 83.8% | commands (12) | 83.8% references (62/74) |
| `tests/test_github_projects_reconcile.py` | `tests/github` | 100.0% | - | 100.0% references (11/11) |
| `tests/test_github_rate_limiter.py` | `tests/github` | 95.8% | core (1) | 95.8% references (46/48) |
| `tests/test_github_secrets.py` | `tests/github` | 58.8% | commands (5) | 58.8% references (20/34) |
| `tests/test_github_session.py` | `tests/github` | 50.0% | core (2) | 50.0% references (3/6) |
| `tests/test_github_ssh.py` | `tests/github` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_gitignore_evaluation.py` | `tests/core` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_golangci_lint_scanner.py` | `tests/security` | 83.3% | ai (1) | 83.3% references (5/6) |
| `tests/test_grafana.py` | `tests/commands` | 85.7% | k8s (1) | 85.7% references (6/7) |
| `tests/test_grafana_dashboards.py` | `tests/grafana` | 66.7% | commands (1) | 66.7% references (2/3) |
| `tests/test_harness_slots.py` | `tests/ai/harness` | 66.7% | ai (1) | 66.7% references (4/6) |
| `tests/test_headless_auth.py` | `tests/config` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_host_sandbox.py` | `tests/sandbox` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_http.py` | `tests/http` | 100.0% | - | 100.0% references (5/5) |
| `tests/test_http_async_client.py` | `tests/http` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_http_broker.py` | `tests/http` | 66.7% | core (1) | 66.7% references (2/3) |
| `tests/test_http_connection_pool.py` | `tests/k8s` | 61.1% | http (6) | 61.1% references (11/18) |
| `tests/test_http_egress.py` | `tests/http` | 12.1% | k8s (4) | 12.1% references (4/33) |
| `tests/test_install_tools.py` | `tests/commands` | 75.0% | tools_lock (1) | 75.0% references (3/4) |
| `tests/test_instruction_generator.py` | `tests/commands` | 66.7% | ai (1) | 66.7% references (2/3) |
| `tests/test_isolation_tripwire.py` | `tests/config` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_item_grounding.py` | `tests/github` | 50.0% | roadmap (1) | 50.0% references (1/2) |
| `tests/test_k8s.py` | `tests/commands/k8s` | 88.0% | security (12) | 88.0% references (198/225) |
| `tests/test_k8s_agents_manifests.py` | `tests/commands/k8s` | 50.0% | k8s (1) | 50.0% references (1/2) |
| `tests/test_k8s_argo_workflows.py` | `tests/tools_lock` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_k8s_argocd_apps.py` | `tests/invariants` | 100.0% | - | Invariant test of committed repo files |
| `tests/test_k8s_argocd_gate.py` | `tests/k8s` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_k8s_argocd_overrides.py` | `tests/k8s` | 100.0% | - | Explicit assignment in #1313 / Phase E |
| `tests/test_k8s_bootstrap.py` | `tests/commands/k8s` | 100.0% | - | 100.0% references (40/40) |
| `tests/test_k8s_chaos_runner.py` | `tests/k8s` | 100.0% | - | 100.0% references (4/4) |
| `tests/test_k8s_cloudflared.py` | `tests/tools_lock` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_k8s_cluster_job_api.py` | `tests/k8s` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_k8s_configmap.py` | `tests/k8s` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_k8s_context.py` | `tests/commands/k8s` | 93.3% | k8s (2) | 93.3% references (42/45) |
| `tests/test_k8s_context_resolution.py` | `tests/k8s` | 44.8% | commands (13) | 44.8% references (13/29) |
| `tests/test_k8s_credentials.py` | `tests/http` | 50.0% | k8s (1) | 50.0% references (1/2) |
| `tests/test_k8s_deploy_stack_urls.py` | `tests/commands/k8s` | 100.0% | - | k8s deploy-stack command tests |
| `tests/test_k8s_devops_runtime.py` | `tests/config` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_k8s_devops_stack.py` | `tests/commands/k8s` | 100.0% | - | 100.0% references (5/5) |
| `tests/test_k8s_doctor.py` | `tests/k8s` | 90.0% | commands/k8s (1) | 90.0% references (9/10) |
| `tests/test_k8s_gitea.py` | `tests/commands/k8s` | 66.7% | k8s (1) | 66.7% references (2/3) |
| `tests/test_k8s_gpu_matrix.py` | `tests/ai` | 33.3% | commands/k8s (1) | 33.3% references (1/3) |
| `tests/test_k8s_gpu_placement.py` | `tests/commands/k8s` | 84.6% | k8s (2) | 84.6% references (11/13) |
| `tests/test_k8s_ipv6_and_proxy_boundaries.py` | `tests/sandbox` | 34.8% | commands/k8s (7) | 34.8% references (8/23) |
| `tests/test_k8s_job_admission_policy.py` | `tests/k8s` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_k8s_llm_gateway.py` | `tests/ai/benchmark` | 20.0% | ai (1) | 20.0% references (1/5) |
| `tests/test_k8s_local_path_placement.py` | `tests/core` | 100.0% | - | No devops_cli references; placed by domain |
| `tests/test_k8s_logging_stack.py` | `tests/commands/k8s` | 85.7% | k8s (4) | 85.7% references (24/28) |
| `tests/test_k8s_logql.py` | `tests/ai/mcp` | 60.0% | k8s (2) | 60.0% references (3/5) |
| `tests/test_k8s_logs_diff_chaos.py` | `tests/k8s` | 72.7% | commands/k8s (3) | 72.7% references (8/11) |
| `tests/test_k8s_manifest_validation.py` | `tests/security` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_k8s_models.py` | `tests/k8s` | 42.9% | ui (2) | 42.9% references (3/7) |
| `tests/test_k8s_monitoring_alerting.py` | `tests/prometheus` | 33.3% | telemetry (1) | 33.3% references (1/3) |
| `tests/test_k8s_monitoring_dashboards.py` | `tests/prometheus` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_k8s_monitoring_integration.py` | `tests/commands/k8s` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_k8s_network_policies.py` | `tests/commands/k8s` | 100.0% | - | 100.0% references (4/4) |
| `tests/test_k8s_networking.py` | `tests/commands/k8s` | 90.9% | k8s (2) | 90.9% references (30/33) |
| `tests/test_k8s_policy.py` | `tests/k8s` | 66.7% | commands/k8s (1) | 66.7% references (2/3) |
| `tests/test_k8s_port_forward_daemon.py` | `tests/k8s` | 66.7% | commands/k8s (3) | 66.7% references (8/12) |
| `tests/test_k8s_proxy_addressing.py` | `tests/commands/k8s` | 60.0% | k8s (4) | 60.0% references (9/15) |
| `tests/test_k8s_proxy_reachability.py` | `tests/k8s` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_k8s_push_secrets.py` | `tests/k8s` | 77.1% | commands/k8s (4) | 77.1% references (27/35) |
| `tests/test_k8s_qdrant_security.py` | `tests/commands/k8s` | 40.0% | k8s (4) | 40.0% references (4/10) |
| `tests/test_k8s_rbac_audit.py` | `tests/commands/k8s` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_k8s_roadmap_service.py` | `tests/server/routes` | 50.0% | telemetry (1) | 50.0% references (1/2) |
| `tests/test_k8s_run_job.py` | `tests/commands/k8s` | 66.7% | k8s (1) | 66.7% references (4/6) |
| `tests/test_k8s_runner.py` | `tests/core` | 100.0% | - | No devops_cli references; placed by domain |
| `tests/test_k8s_runtime_cmd.py` | `tests/commands/k8s` | 100.0% | - | 100.0% references (10/10) |
| `tests/test_k8s_security_stream.py` | `tests/k8s` | 73.3% | ai/mcp (3) | 73.3% references (11/15) |
| `tests/test_k8s_service.py` | `tests/k8s` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_k8s_service_proxy.py` | `tests/k8s` | 96.2% | commands/k8s (1) | 96.2% references (25/26) |
| `tests/test_k8s_template.py` | `tests/k8s` | 58.3% | commands/k8s (3) | 58.3% references (7/12) |
| `tests/test_k8s_tempo.py` | `tests/commands/k8s` | 87.5% | k8s (1) | 87.5% references (7/8) |
| `tests/test_k8s_tls.py` | `tests/commands/k8s` | 83.3% | crypto (1) | 83.3% references (5/6) |
| `tests/test_k8s_valkey_stack.py` | `tests/k8s` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_k8s_volume_move.py` | `tests/k8s` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_k8s_volume_reclaim.py` | `tests/commands/k8s` | 92.9% | k8s (1) | 92.9% references (13/14) |
| `tests/test_kb.py` | `tests/ai` | 75.0% | ai/rag (1) | 75.0% references (3/4) |
| `tests/test_kb_manuals_metadata.py` | `tests/review` | 80.0% | ai (1) | 80.0% references (4/5) |
| `tests/test_kustomize.py` | `tests/commands` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_language_catalogs.py` | `tests/lang` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_library_drift_auditor.py` | `tests/ai/analyze` | 40.0% | ai/library (1) | 40.0% references (2/5) |
| `tests/test_library_ingest.py` | `tests/ai/library` | 50.0% | commands (1) | 50.0% references (1/2) |
| `tests/test_library_vector_tier.py` | `tests/commands` | 42.9% | ai/rag (4) | 42.9% references (6/14) |
| `tests/test_llm_pool_metrics.py` | `tests/ai` | 40.0% | commands (1) | 40.0% references (2/5) |
| `tests/test_load_and_pipeline.py` | `tests/commands` | 100.0% | - | 100.0% references (6/6) |
| `tests/test_main_dry_run.py` | `tests/core` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_mcp.py` | `tests/ai/mcp` | 76.5% | commands (3) | 76.5% references (13/17) |
| `tests/test_memory_profiler.py` | `tests/commands` | 80.0% | telemetry (2) | 80.0% references (8/10) |
| `tests/test_merge_readiness.py` | `tests/github` | 100.0% | - | 100.0% references (4/4) |
| `tests/test_metadata.py` | `tests/config` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_model_bundle.py` | `tests/ai` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_model_contract.py` | `tests/ai/client` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_model_fixture.py` | `tests/ai/client` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_net_construct_rules.py` | `tests/commands` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_network_security_and_trace_correlation.py` | `tests/security` | 40.0% | telemetry (2) | 40.0% references (2/5) |
| `tests/test_ollama_dynamic_leasing.py` | `tests/ai/client` | 88.9% | telemetry (1) | 88.9% references (8/9) |
| `tests/test_openblas_worker_threads.py` | `tests/core` | 100.0% | - | No devops_cli references; placed by domain |
| `tests/test_openspec_command.py` | `tests/core` | 100.0% | - | No devops_cli references; placed by domain |
| `tests/test_openspec_contract.py` | `tests/tools_lock` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_openspec_gate.py` | `tests/openspec` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_openspec_scaffold.py` | `tests/commands` | 50.0% | tools_lock (1) | 50.0% references (1/2) |
| `tests/test_openspec_tool.py` | `tests/openspec` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_osv_scanner.py` | `tests/security` | 42.9% | review (2) | 42.9% references (3/7) |
| `tests/test_otel_command_coverage.py` | `tests/telemetry` | 100.0% | - | Explicit assignment in #1313 / Phase E |
| `tests/test_output.py` | `tests/ai` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_per_test_timeout.py` | `tests/config` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_personas.py` | `tests/ai/personas` | 100.0% | - | 100.0% references (4/4) |
| `tests/test_pipeline_context_budget.py` | `tests/ai/rag` | 46.7% | ai/agents (3) | 46.7% references (7/15) |
| `tests/test_pr_check_verdict.py` | `tests/github` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_pr_cmd.py` | `tests/commands` | 100.0% | github (26) | 100.0% references (61/104) |
| `tests/test_pr_hardening_report.py` | `tests/commands` | 100.0% | - | 100.0% references (7/7) |
| `tests/test_pr_status.py` | `tests/commands` | 61.5% | roadmap (4) | 61.5% references (8/13) |
| `tests/test_pr_title_labels.py` | `tests/commands` | 50.0% | roadmap (5) | 50.0% references (7/14) |
| `tests/test_pr_update.py` | `tests/commands` | 75.0% | ai/mcp (1) | 75.0% references (6/8) |
| `tests/test_process.py` | `tests/core` | 100.0% | - | 100.0% references (5/5) |
| `tests/test_process_contract.py` | `tests/core` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_process_hardening.py` | `tests/core` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_prometheus.py` | `tests/commands` | 100.0% | - | 100.0% references (10/10) |
| `tests/test_prometheus_models.py` | `tests/models` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_prompt_injection.py` | `tests/security` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_prompt_programmatic_functions.py` | `tests/ai` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_promql_analysis.py` | `tests/commands` | 66.7% | prometheus (2) | 66.7% references (4/6) |
| `tests/test_public_export_surface.py` | `tests/core` | 100.0% | - | No devops_cli references; placed by domain |
| `tests/test_pydantic_agent.py` | `tests/ai/agents` | 88.9% | ai/toolsets (2) | 88.9% references (24/27) |
| `tests/test_pydantic_ai_concurrency.py` | `tests/ai/agents` | 75.0% | ai (1) | 75.0% references (3/4) |
| `tests/test_pydantic_ai_exceptions.py` | `tests/ai/agents` | 85.7% | docs (1) | 85.7% references (6/7) |
| `tests/test_pydantic_ai_format_prompt.py` | `tests/ai` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_pydantic_ai_function_signature.py` | `tests/ai` | 66.7% | ai/agents (2) | 66.7% references (4/6) |
| `tests/test_pydantic_ai_mcp.py` | `tests/ai/mcp` | 54.5% | ai/agents (3) | 54.5% references (6/11) |
| `tests/test_pydantic_ai_native_capabilities.py` | `tests/ai/agents` | 66.7% | ai (1) | 66.7% references (2/3) |
| `tests/test_pydantic_ai_ollama.py` | `tests/ai/models` | 68.8% | ai/agents (3) | 68.8% references (11/16) |
| `tests/test_pydantic_ai_profiles_and_providers.py` | `tests/ai` | 57.1% | ai/providers (1) | 57.1% references (4/7) |
| `tests/test_pydantic_ai_retries.py` | `tests/ai/retries` | 50.0% | ai/client (1) | 50.0% references (1/2) |
| `tests/test_pydantic_ai_settings.py` | `tests/ai/settings` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_pydantic_ai_tools.py` | `tests/ai/tools` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_pydantic_ai_toolsets.py` | `tests/ai/agents` | 50.0% | ai/tools (1) | 50.0% references (2/4) |
| `tests/test_pydantic_ai_workflows.py` | `tests/ai` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_qdrant_cluster_addressing.py` | `tests/ai/rag` | 73.7% | k8s (5) | 73.7% references (14/19) |
| `tests/test_qdrant_timeout_setting.py` | `tests/ai/rag` | 66.7% | ai/tools (1) | 66.7% references (4/6) |
| `tests/test_rag_chunker.py` | `tests/ai` | 66.7% | ai/rag (1) | 66.7% references (2/3) |
| `tests/test_rag_cli.py` | `tests/ai/rag` | 63.2% | commands (6) | 63.2% references (12/19) |
| `tests/test_rag_drift.py` | `tests/ai/rag` | 100.0% | - | 100.0% references (6/6) |
| `tests/test_rag_embedding_model_compatibility.py` | `tests/ai/rag` | 100.0% | - | 100.0% references (6/6) |
| `tests/test_rag_embeddings.py` | `tests/ai/rag` | 71.4% | telemetry (2) | 71.4% references (15/21) |
| `tests/test_rag_hybrid_search.py` | `tests/ai/rag` | 88.9% | ai (1) | 88.9% references (8/9) |
| `tests/test_rag_indexer_retriever.py` | `tests/ai/rag` | 85.7% | ai (1) | 85.7% references (6/7) |
| `tests/test_rag_investigator.py` | `tests/ai/rag` | 100.0% | - | 100.0% references (27/27) |
| `tests/test_rag_kb_sync.py` | `tests/ai/rag` | 72.7% | ai (1) | 72.7% references (8/11) |
| `tests/test_rag_loopback_policy.py` | `tests/ai/rag` | 66.7% | ai/client (1) | 66.7% references (2/3) |
| `tests/test_rag_metadata_extraction.py` | `tests/ai/rag` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_rag_multi_project_indexer.py` | `tests/ai/rag` | 100.0% | - | 100.0% references (4/4) |
| `tests/test_rag_polyglot_chunker.py` | `tests/ai/rag` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_rag_qdrant.py` | `tests/ai/rag` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_rag_qdrant_keyring.py` | `tests/ai/rag` | 100.0% | - | 100.0% references (6/6) |
| `tests/test_rag_qdrant_server_label.py` | `tests/ai/rag` | 71.4% | http (2) | 71.4% references (5/7) |
| `tests/test_rag_qdrant_span.py` | `tests/ai/rag` | 50.0% | telemetry (1) | 50.0% references (1/2) |
| `tests/test_rag_query_telemetry.py` | `tests/ai/rag` | 70.0% | telemetry (3) | 70.0% references (7/10) |
| `tests/test_rag_retriever_filters.py` | `tests/ai/rag` | 100.0% | - | 100.0% references (4/4) |
| `tests/test_rag_rrf.py` | `tests/ai/rag` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_renovate_config.py` | `tests/core` | 100.0% | - | No devops_cli references; placed by domain |
| `tests/test_repomap.py` | `tests/ai` | 83.3% | ai/ast (1) | 83.3% references (5/6) |
| `tests/test_repos.py` | `tests/commands` | 75.4% | core (15) | 75.4% references (46/61) |
| `tests/test_repos_worktrees.py` | `tests/git` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_repos_worktrees_add.py` | `tests/core` | 100.0% | - | No devops_cli references; placed by domain |
| `tests/test_repos_worktrees_reclaim.py` | `tests/git` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_resource_schemas.py` | `tests/models` | 100.0% | - | 100.0% references (9/9) |
| `tests/test_response_cache.py` | `tests/ai/client` | 40.0% | commands (2) | 40.0% references (2/5) |
| `tests/test_review.py` | `tests/ai/review` | 66.7% | ai (6) | ai/review workflow; avoids collision with commands/test_review.py |
| `tests/test_review_adjudication.py` | `tests/commands` | 54.5% | ai/review (3) | 54.5% references (6/11) |
| `tests/test_review_admission.py` | `tests/ai/review` | 32.4% | review (11) | 32.4% references (12/37) |
| `tests/test_review_advisory_backing.py` | `tests/ai` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_review_backend_activity.py` | `tests/ai/review` | 66.7% | commands (1) | 66.7% references (2/3) |
| `tests/test_review_canary.py` | `tests/security` | 64.3% | ai/review (3) | 64.3% references (9/14) |
| `tests/test_review_console_report.py` | `tests/ai/review` | 80.0% | ai (1) | 80.0% references (4/5) |
| `tests/test_review_deduplication.py` | `tests/ai/review` | 66.7% | ai (1) | 66.7% references (2/3) |
| `tests/test_review_defects.py` | `tests/ai` | 44.4% | ai/review (3) | 44.4% references (4/9) |
| `tests/test_review_defects_comments.py` | `tests/ai/review` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_review_defects_infra.py` | `tests/ai/review` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_review_defects_languages.py` | `tests/ai/review` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_review_defenses_and_verification.py` | `tests/ai/review` | 33.3% | ai/agents (1) | 33.3% references (2/6) |
| `tests/test_review_diff.py` | `tests/review` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_review_dry_run_preview.py` | `tests/core` | 50.0% | ai/client (1) | 50.0% references (2/4) |
| `tests/test_review_exporter.py` | `tests/ai/review` | 66.7% | commands (1) | 66.7% references (2/3) |
| `tests/test_review_filed_findings.py` | `tests/github` | 50.0% | review (1) | 50.0% references (1/2) |
| `tests/test_review_finding_losses.py` | `tests/ai` | 54.5% | ai/review (2) | 54.5% references (6/11) |
| `tests/test_review_group_analysis.py` | `tests/review` | 55.0% | ai/review (7) | 55.0% references (22/40) |
| `tests/test_review_history.py` | `tests/ai/review` | 85.7% | ai (1) | 85.7% references (6/7) |
| `tests/test_review_location_paths.py` | `tests/ai` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_review_loop_hardening.py` | `tests/ai` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_review_manifests.py` | `tests/review` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_review_page_line_numbers.py` | `tests/review` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_review_path.py` | `tests/ai/review` | 42.9% | review (2) | 42.9% references (3/7) |
| `tests/test_review_path_classes.py` | `tests/ai/analyze` | 50.0% | ai/review (1) | 50.0% references (1/2) |
| `tests/test_review_path_routing.py` | `tests/ai/review` | 36.4% | commands (4) | 36.4% references (4/11) |
| `tests/test_review_pipeline.py` | `tests/ai/review` | 43.8% | ai (4) | 43.8% references (7/16) |
| `tests/test_review_pipeline_go.py` | `tests/security` | 50.0% | ai/review (1) | 50.0% references (2/4) |
| `tests/test_review_pr_post.py` | `tests/commands` | 71.4% | ai/review (2) | 71.4% references (10/14) |
| `tests/test_review_profile.py` | `tests/ai/review` | 42.9% | ai (2) | 42.9% references (6/14) |
| `tests/test_review_project_conventions.py` | `tests/ai/review` | 66.7% | ai/rag (1) | 66.7% references (2/3) |
| `tests/test_review_prompt_adversaries.py` | `tests/review` | 44.4% | ai/review (2) | 44.4% references (4/9) |
| `tests/test_review_prompt_guardrails.py` | `tests/ai` | 60.0% | ai/review (1) | 60.0% references (3/5) |
| `tests/test_review_regression_harness.py` | `tests/ai/review` | 50.0% | ai (1) | 50.0% references (1/2) |
| `tests/test_review_reply_caps.py` | `tests/ai/client` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_review_report_integrity.py` | `tests/ai/review` | 25.0% | ai (1) | 25.0% references (1/4) |
| `tests/test_review_report_summary.py` | `tests/ai/review` | 66.7% | ai (1) | 66.7% references (4/6) |
| `tests/test_review_repos.py` | `tests/ai/review` | 66.7% | ai/analyze (1) | 66.7% references (2/3) |
| `tests/test_review_ruff_mypy_evidence.py` | `tests/security` | 42.9% | ai/review (2) | 42.9% references (3/7) |
| `tests/test_review_rules_pack.py` | `tests/commands` | 40.0% | core (1) | 40.0% references (2/5) |
| `tests/test_review_runner.py` | `tests/ai/review` | 73.1% | git (7) | 73.1% references (38/52) |
| `tests/test_review_sample_validation.py` | `tests/ai/review` | 57.1% | ai (2) | 57.1% references (4/7) |
| `tests/test_review_samples.py` | `tests/ai/review` | 50.0% | commands (1) | 50.0% references (1/2) |
| `tests/test_review_scope.py` | `tests/commands` | 37.5% | ai/review (2) | 37.5% references (3/8) |
| `tests/test_review_score.py` | `tests/security` | 50.0% | ai (1) | 50.0% references (2/4) |
| `tests/test_review_security_tools.py` | `tests/ai/review` | 20.0% | ai (1) | 20.0% references (1/5) |
| `tests/test_review_session_store.py` | `tests/ai` | 33.3% | review (1) | 33.3% references (1/3) |
| `tests/test_review_stage_flags.py` | `tests/commands` | 77.8% | ai/review (2) | 77.8% references (7/9) |
| `tests/test_review_state.py` | `tests/ai` | 50.0% | review (1) | 50.0% references (1/2) |
| `tests/test_review_static_analyzers.py` | `tests/ai/review` | 45.5% | security (3) | 45.5% references (5/11) |
| `tests/test_review_symbol_delta.py` | `tests/ai/review` | 40.0% | git (6) | 40.0% references (6/15) |
| `tests/test_review_syntax_masking.py` | `tests/review` | 50.0% | ai/analyze (2) | 50.0% references (3/6) |
| `tests/test_review_taxonomy_and_severity.py` | `tests/ai/review` | 66.7% | ai (1) | 66.7% references (2/3) |
| `tests/test_review_template_sweep.py` | `tests/ai/review` | 55.6% | commands (2) | 55.6% references (5/9) |
| `tests/test_review_tool_runs.py` | `tests/security` | 54.5% | ai/review (5) | 54.5% references (12/22) |
| `tests/test_review_tool_sandbox.py` | `tests/ai/review` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_review_untrusted_tree.py` | `tests/review` | 20.0% | ai (6) | 20.0% references (7/35) |
| `tests/test_review_verification.py` | `tests/ai` | 42.9% | ai/review (2) | 42.9% references (3/7) |
| `tests/test_review_worktree_regression.py` | `tests/git` | 37.5% | commands (4) | 37.5% references (6/16) |
| `tests/test_roadmap_agent_run.py` | `tests/ai/client` | 33.3% | ai/spend (1) | 33.3% references (1/3) |
| `tests/test_roadmap_alternatives.py` | `tests/roadmap` | 62.5% | ai/client (1) | 62.5% references (5/8) |
| `tests/test_roadmap_commit_title.py` | `tests/roadmap` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_roadmap_dry_runs.py` | `tests/roadmap` | 83.3% | commands (2) | 83.3% references (20/24) |
| `tests/test_roadmap_duplicate_eval.py` | `tests/roadmap` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_roadmap_github_store.py` | `tests/roadmap` | 66.7% | github (1) | 66.7% references (2/3) |
| `tests/test_roadmap_implement_checks.py` | `tests/core` | 100.0% | - | No devops_cli references; placed by domain |
| `tests/test_roadmap_implement_command.py` | `tests/roadmap` | 75.0% | ai/client (1) | 75.0% references (3/4) |
| `tests/test_roadmap_implement_job.py` | `tests/roadmap` | 60.0% | ai/client (1) | 60.0% references (3/5) |
| `tests/test_roadmap_implement_planned.py` | `tests/roadmap` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_roadmap_implement_planned_run.py` | `tests/core` | 100.0% | - | No devops_cli references; placed by domain |
| `tests/test_roadmap_implement_records.py` | `tests/roadmap` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_roadmap_implement_selection.py` | `tests/roadmap` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_roadmap_implement_shell_refusal.py` | `tests/roadmap` | 66.7% | ai (1) | 66.7% references (2/3) |
| `tests/test_roadmap_implement_step.py` | `tests/roadmap` | 66.7% | ai/client (1) | 66.7% references (4/6) |
| `tests/test_roadmap_implement_step_format.py` | `tests/roadmap` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_roadmap_implement_step_own_text.py` | `tests/roadmap` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_roadmap_implement_step_repair.py` | `tests/roadmap` | 66.7% | security (1) | 66.7% references (2/3) |
| `tests/test_roadmap_implement_step_tests_kept.py` | `tests/roadmap` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_roadmap_implement_step_ticks.py` | `tests/roadmap` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_roadmap_implement_submit.py` | `tests/roadmap` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_roadmap_implement_test_names.py` | `tests/roadmap` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_roadmap_implement_tool_log.py` | `tests/roadmap` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_roadmap_intake.py` | `tests/roadmap` | 52.4% | github (4) | 52.4% references (11/21) |
| `tests/test_roadmap_intake_checks.py` | `tests/roadmap` | 100.0% | - | 100.0% references (4/4) |
| `tests/test_roadmap_planned.py` | `tests/roadmap` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_roadmap_refine.py` | `tests/roadmap` | 50.0% | commands (2) | 50.0% references (5/10) |
| `tests/test_roadmap_refine_investigation.py` | `tests/roadmap` | 66.7% | ai/client (1) | 66.7% references (4/6) |
| `tests/test_roadmap_return.py` | `tests/roadmap` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_roadmap_run.py` | `tests/roadmap` | 57.9% | ai/mcp (2) | 57.9% references (11/19) |
| `tests/test_roadmap_stage_apply.py` | `tests/roadmap` | 100.0% | - | 100.0% references (5/5) |
| `tests/test_roadmap_stage_command.py` | `tests/roadmap` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_roadmap_stage_job.py` | `tests/roadmap` | 80.0% | telemetry (1) | 80.0% references (4/5) |
| `tests/test_roadmap_stage_plan.py` | `tests/roadmap` | 40.0% | ai/client (2) | 40.0% references (4/10) |
| `tests/test_roadmap_stage_planned.py` | `tests/roadmap` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_roadmap_stage_reconcile.py` | `tests/roadmap` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_roadmap_stage_selection.py` | `tests/roadmap` | 100.0% | - | 100.0% references (4/4) |
| `tests/test_roadmap_stage_settings.py` | `tests/roadmap` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_roadmap_stage_title.py` | `tests/roadmap` | 100.0% | - | 100.0% references (4/4) |
| `tests/test_roadmap_store_contract.py` | `tests/roadmap` | 75.0% | github (1) | 75.0% references (3/4) |
| `tests/test_ruff_complexity_cap.py` | `tests/commands` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_run_comparison.py` | `tests/ai` | 50.0% | commands (1) | 50.0% references (1/2) |
| `tests/test_run_store.py` | `tests/ai` | 37.5% | commands (2) | 37.5% references (3/8) |
| `tests/test_runtime_input_guards.py` | `tests/security` | 50.0% | ai/diff (1) | 50.0% references (2/4) |
| `tests/test_sandbox_lifecycle.py` | `tests/commands` | 48.1% | sandbox (5) | 48.1% references (13/27) |
| `tests/test_sandbox_logs.py` | `tests/commands` | 58.8% | sandbox (7) | 58.8% references (10/17) |
| `tests/test_sandbox_metrics.py` | `tests/sandbox` | 70.0% | commands (12) | 70.0% references (28/40) |
| `tests/test_sandbox_networking.py` | `tests/commands` | 33.3% | sandbox (2) | 33.3% references (2/6) |
| `tests/test_sandbox_policy_properties.py` | `tests/core` | 40.0% | sandbox (2) | 40.0% references (2/5) |
| `tests/test_sandbox_probe.py` | `tests/sandbox` | 69.2% | commands (4) | 69.2% references (9/13) |
| `tests/test_sandbox_seccomp.py` | `tests/sandbox` | 100.0% | - | 100.0% references (4/4) |
| `tests/test_sandbox_tool_executor.py` | `tests/sandbox` | 50.0% | security (1) | 50.0% references (1/2) |
| `tests/test_sandbox_traces.py` | `tests/telemetry` | 75.0% | commands (1) | 75.0% references (6/8) |
| `tests/test_sbom.py` | `tests/security` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_scan.py` | `tests/commands` | 84.2% | security (2) | 84.2% references (16/19) |
| `tests/test_scan_complexity.py` | `tests/core` | 50.0% | security (1) | 50.0% references (1/2) |
| `tests/test_scan_injection.py` | `tests/commands` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_scan_outcomes_and_gating.py` | `tests/commands` | 64.7% | security (5) | 64.7% references (11/17) |
| `tests/test_scanner_contract.py` | `tests/security` | 70.0% | review (2) | 70.0% references (7/10) |
| `tests/test_scanner_tool_executor.py` | `tests/security` | 84.6% | ai/review (1) | 84.6% references (11/13) |
| `tests/test_schema_reflection.py` | `tests/ai/client` | 66.7% | ai (1) | 66.7% references (2/3) |
| `tests/test_secops.py` | `tests/security` | 75.0% | ai (1) | 75.0% references (6/8) |
| `tests/test_secret_resolution.py` | `tests/security` | 72.4% | http (8) | 72.4% references (21/29) |
| `tests/test_security_bandit.py` | `tests/commands` | 40.0% | security (2) | 40.0% references (2/5) |
| `tests/test_security_gitleaks.py` | `tests/security` | 60.0% | ai (1) | 60.0% references (3/5) |
| `tests/test_security_kubeconform.py` | `tests/security` | 50.0% | ai (1) | 50.0% references (2/4) |
| `tests/test_security_kubelinter.py` | `tests/security` | 75.0% | ai (1) | 75.0% references (3/4) |
| `tests/test_security_sandbox_and_protection.py` | `tests/ai/agents` | 18.8% | core (3) | 18.8% references (3/16) |
| `tests/test_security_semgrep.py` | `tests/security` | 50.0% | ai/review (4) | 50.0% references (7/14) |
| `tests/test_security_threat_intel.py` | `tests/security` | 50.0% | valkey (1) | 50.0% references (1/2) |
| `tests/test_security_uv_audit.py` | `tests/security` | 66.7% | ai (1) | 66.7% references (2/3) |
| `tests/test_security_zizmor.py` | `tests/commands` | 50.0% | security (2) | 50.0% references (2/4) |
| `tests/test_semgrep_registry.py` | `tests/security` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_server.py` | `tests/server` | 40.0% | commands (1) | 40.0% references (2/5) |
| `tests/test_server_service.py` | `tests/telemetry` | 44.4% | server (3) | 44.4% references (4/9) |
| `tests/test_server_stream.py` | `tests/server` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_service_client_configured_urls.py` | `tests/ai` | 66.7% | ai/client (1) | 66.7% references (4/6) |
| `tests/test_service_limits.py` | `tests/github` | 36.4% | roadmap (3) | 36.4% references (4/11) |
| `tests/test_service_status.py` | `tests/telemetry` | 75.0% | commands (3) | 75.0% references (9/12) |
| `tests/test_service_url_defaults.py` | `tests/config` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ssh.py` | `tests/crypto` | 100.0% | - | 100.0% references (10/10) |
| `tests/test_ssh_host_keys.py` | `tests/git` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_stack_dashboards.py` | `tests/commands/k8s` | 50.0% | prometheus (1) | 50.0% references (1/2) |
| `tests/test_streaming_serializer.py` | `tests/output` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_structural_positional_oracles.py` | `tests/ai` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_subprocess_env_boundary.py` | `tests/core` | 100.0% | - | Explicit assignment in #1313 / Phase E |
| `tests/test_subprocess_env_file_write.py` | `tests/core` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_subprocess_env_gh_kubectl.py` | `tests/core` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_subprocess_env_uv_npm.py` | `tests/core` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_subsystem_containment_and_redaction.py` | `tests/commands/k8s` | 37.5% | ai/agents (1) | 37.5% references (3/8) |
| `tests/test_suite_refuses_real_programs.py` | `tests/invariants` | 100.0% | - | Explicit assignment in #1313 / Phase E |
| `tests/test_support_builders.py` | `tests/ai/review` | 33.3% | ai (1) | 33.3% references (1/3) |
| `tests/test_support_hung_children.py` | `tests/core` | 100.0% | - | No devops_cli references; placed by domain |
| `tests/test_support_waits.py` | `tests/core` | 100.0% | - | No devops_cli references; placed by domain |
| `tests/test_survey_capabilities.py` | `tests/survey` | 75.0% | roadmap (1) | 75.0% references (3/4) |
| `tests/test_survey_cmd.py` | `tests/commands` | 100.0% | commands (1) | 100.0% references (1/2) |
| `tests/test_survey_dependencies.py` | `tests/survey` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_swallowed_failures_ratchet.py` | `tests/invariants` | 100.0% | - | Explicit assignment in #1313 / Phase E |
| `tests/test_telemetry.py` | `tests/telemetry` | 80.0% | ai/client (2) | 80.0% references (8/10) |
| `tests/test_telemetry_cmd.py` | `tests/commands` | 100.0% | commands (1) | 100.0% references (2/3) |
| `tests/test_telemetry_collector_export.py` | `tests/telemetry` | 66.7% | k8s (2) | 66.7% references (4/6) |
| `tests/test_telemetry_deduplication.py` | `tests/core` | 50.0% | telemetry (1) | 50.0% references (1/2) |
| `tests/test_telemetry_instruments.py` | `tests/telemetry` | 46.2% | ai (2) | 46.2% references (6/13) |
| `tests/test_telemetry_llm_content.py` | `tests/telemetry` | 60.0% | ai/agents (1) | 60.0% references (6/10) |
| `tests/test_telemetry_logfire.py` | `tests/telemetry` | 62.5% | commands (1) | 62.5% references (5/8) |
| `tests/test_telemetry_logging_bridge.py` | `tests/telemetry` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_telemetry_metrics.py` | `tests/telemetry` | 50.0% | server (2) | 50.0% references (3/6) |
| `tests/test_telemetry_profile.py` | `tests/commands` | 76.2% | core (4) | 76.2% references (16/21) |
| `tests/test_telemetry_semconv.py` | `tests/telemetry` | 66.7% | commands (1) | 66.7% references (2/3) |
| `tests/test_telemetry_shutdown_sync.py` | `tests/telemetry` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_template_rendering.py` | `tests/core` | 100.0% | - | 100.0% references (3/3) |
| `tests/test_test_module_independence.py` | `tests/core` | 100.0% | - | No devops_cli references; placed by domain |
| `tests/test_test_runner.py` | `tests/commands` | 92.3% | telemetry (1) | 92.3% references (12/13) |
| `tests/test_test_selection.py` | `tests/commands` | 50.0% | core (2) | 50.0% references (3/6) |
| `tests/test_tf.py` | `tests/commands` | 80.0% | security (5) | 80.0% references (28/35) |
| `tests/test_tf_analysis.py` | `tests/tf` | 85.7% | commands (1) | 85.7% references (6/7) |
| `tests/test_tf_cost.py` | `tests/tf` | 61.5% | ai/mcp (3) | 61.5% references (8/13) |
| `tests/test_tf_notify_plan.py` | `tests/commands` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_thinking.py` | `tests/ai` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_thinking_providers.py` | `tests/ai` | 57.1% | ai/client (3) | 57.1% references (4/7) |
| `tests/test_third_party_telemetry.py` | `tests/core` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_tls_cmd.py` | `tests/commands` | 100.0% | crypto (1) | 100.0% references (9/10) |
| `tests/test_tool_executor_contract.py` | `tests/ai` | 25.0% | sandbox (1) | 25.0% references (1/4) |
| `tests/test_tools_lock.py` | `tests/tools_lock` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_trace_propagation.py` | `tests/telemetry` | 66.7% | core (2) | 66.7% references (4/6) |
| `tests/test_treesitter_engine.py` | `tests/ai/ast` | 75.0% | ai (1) | 75.0% references (3/4) |
| `tests/test_treesitter_native_symbols.py` | `tests/ai/ast` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_tuicr_config.py` | `tests/config` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_ui_dashboard.py` | `tests/ui` | 76.5% | commands (3) | 76.5% references (13/17) |
| `tests/test_ui_reactive.py` | `tests/ui` | 85.7% | commands (1) | 85.7% references (12/14) |
| `tests/test_ui_sparklines.py` | `tests/ui` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_ui_telemetry_panel.py` | `tests/ui` | 83.3% | k8s (1) | 83.3% references (5/6) |
| `tests/test_ui_waterfall_modal.py` | `tests/ui` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_url_credential_masking.py` | `tests/ai/client` | 60.0% | security (2) | 60.0% references (3/5) |
| `tests/test_uv.py` | `tests/commands` | 100.0% | - | 100.0% references (7/7) |
| `tests/test_validation.py` | `tests/core` | 81.8% | http (2) | 81.8% references (18/22) |
| `tests/test_valkey.py` | `tests/commands` | 80.6% | valkey (3) | 80.6% references (25/31) |
| `tests/test_valkey_cache_tier.py` | `tests/valkey` | 57.1% | ai/rag (1) | 57.1% references (4/7) |
| `tests/test_vault_broker.py` | `tests/security` | 100.0% | - | 100.0% references (4/4) |
| `tests/test_vault_cmd.py` | `tests/commands` | 100.0% | ai/mcp (3) | 100.0% references (17/23) |
| `tests/test_verdict_polarity.py` | `tests/review` | 50.0% | ai/review (1) | 50.0% references (2/4) |
| `tests/test_verdict_writers.py` | `tests/ai` | 40.0% | ai/mcp (1) | 40.0% references (2/5) |
| `tests/test_vulnerability_lookup.py` | `tests/security` | 61.5% | ai/review (2) | 61.5% references (8/13) |
| `tests/test_watchers.py` | `tests/watchers` | 100.0% | - | 100.0% references (2/2) |
| `tests/test_workflow_contracts.py` | `tests/invariants` | 100.0% | - | Invariant test of committed repo files |
| `tests/test_workload_sandbox.py` | `tests/commands` | 40.0% | telemetry (2) | 40.0% references (2/5) |
| `tests/test_workspace.py` | `tests/commands` | 81.2% | core (3) | 81.2% references (13/16) |
| `tests/test_workspace_cleanup.py` | `tests/core` | 100.0% | - | 100.0% references (1/1) |
| `tests/test_zero_plaintext_invariants.py` | `tests/commands` | 100.0% | - | 100.0% references (1/1) |
