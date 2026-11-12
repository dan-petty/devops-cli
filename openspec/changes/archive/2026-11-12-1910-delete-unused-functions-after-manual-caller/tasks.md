# Tasks

## 1. Decide each symbol that only tests call

Kind: refactor. Reads: the output of vulture on `src`, filtered as the audit script `dead_code_tests.py` filters it.

- [x] 1.1 Run `uvx vulture src` and keep the rows with no decorator, one occurrence of the name in `src` and a test that names it: 129 rows. Decide each row and each name of the issue list as deleted or kept, and write each kept name with its reason in design.md
  - Verification: `$ uv run devops openspec check`

## 2. Delete the dead symbols of the AI package

Kind: refactor. Changes: `src/devops_cli/ai/`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py` and their tests.

- [x] 2.1 Delete `ai/agents/capabilities.py`, the prewarm wrappers, the async stream sanitizer, the snippet packer, the explanation Markdown, the contract loader, the domain schema hydrator and its prefix table, the dead subscription methods, the `Embedder` class with the engine wrapper, the document chunk indexer, the stage flag check, the review pipeline helpers, the pool methods, the request preview, the prompt truncation, `unique_items`, the run index list, the error summary, the pricing removal and `argo_app_status`, with the tests whose subject they are
  - Verification: `$ ! git grep -n -w -e SystemReminders -e prewarm_async -e async_sanitize_stream -e pack_snippets -e get_explanation_markdown -e load_from_dir -e DomainSchemaHydrator -e to_embedder -e index_doc_chunks -e any_enabled -e _review_worker_count -e _llm_request_preview -e _truncate_for_prompt -e unique_items -e format_error_summary -e remove_custom_pricing src/ tests/`
  - Verification: `$ ! git grep -n -w argo_app_status src/devops_cli/ai tests/security`
- [x] 2.2 Delete the names of the issue list in the review modules: `_unique_preserve_order`, `record_rejection`, `_tokenize_title`, `less_severe` and `ReviewResult.merge`
  - Verification: `$ ! git grep -n -w -e _unique_preserve_order -e record_rejection -e _tokenize_title -e less_severe -e merged_findings src/`

## 3. Delete the dead symbols of the other packages

Kind: refactor. Changes: `src/devops_cli/` outside `ai/` and the tests of each symbol.

- [x] 3.1 Delete `k8s/chaos_runner.py` and `output/table_builder.py`, the three Argo CD list methods, the seven command builders, the two project metadata getters, two validators, the managed key name, three Docker engine methods, the Grafana serialiser, the LogQL line evaluation, four manifest plans, `main_entry`, `is_on_merged_code`, two prompt-injection helpers, three format readers, four lease registry methods, the snapshot staleness check and the command helpers `_apply_symbol_delta_to_meta`, `_build_port_forward_details`, `_resolve_workspace_file`, `_tally_findings` and `_render_logs_json`
  - Verification: `$ ! git grep -n -w -e ChaosFaultRunner -e build_structured_table -e list_application_sets -e build_tofu_cmd -e get_project_name -e validate_session_id -e format_managed_key_filename -e wait_container -e to_grafana_json -e evaluate_log_lines -e plan_k8s_teardown_stack -e main_entry -e is_on_merged_code -e escape_delimiters -e _extract_yaml_strings -e renew_expiring -e is_stale -e _tally_findings -e _render_logs_json src/ tests/`
- [x] 3.2 Delete `should_ignore_dir`, `_is_numbered`, `_extract_policy_include_email` and `WorkloadSandboxEngine.traces` of the issue list
  - Verification: `$ ! git grep -n -w -e should_ignore_dir -e _is_numbered -e _extract_policy_include_email -e resolve_trace_spans src/devops_cli/sandbox/engine.py src/devops_cli/argo src/devops_cli/review src/devops_cli/cloudflare`

## 4. Delete the orphans and keep the ratchet current

Kind: refactor. Changes: `src/devops_cli/config/`, `src/devops_cli/models/vault.py`, `tests/fixtures/swallowed_failures_ceilings.json`, `tests/invariants/test_architectural_invariants.py`.

- [x] 4.1 Run vulture again and delete each name that only a deleted symbol used: helpers, classes, constants, defaults and one tool message
  - Verification: `$ ! git grep -n -w -e DEFAULT_PLAN_REMINDER_ID -e DEFAULT_EMBEDDING_MODEL_NAME -e CONST_MCP_DOMAINS -e VaultLeaseReport -e line_matches_query -e build_iac_cmd src/ tests/`
- [x] 4.2 Lower the swallowed-failures ceilings, and drop the deleted chaos runner from the invariant's module list
  - Verification: `$ uv run python -c "import sys; from tests.gate.swallowed_failures import main; sys.exit(main([]))"`

## 5. Check the tree

Kind: refactor.

- [x] 5.1 Type-check `src` as the gate does
  - Verification: `$ uv run mypy --python-version 3.14 --strict src`
- [x] 5.2 Run the tests of the changed test files
  - Verification: `$ uv run devops ci test tests/ai tests/security tests/docker tests/config tests/crypto tests/review tests/ui`

## Workflow follow-up

- #5148 deletes the dead code that this change keeps for a spec decision, a standards change, a test rewrite or the end of other open work.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
