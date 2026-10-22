# Task: Delete the Tombstone Tests and Trial a Dead-Code Tool (#1871)

**Issue**: [#1871](https://github.com/dan-petty/devops-cli/issues/1871)
**Scope**: scope/ci
**Feasibility**: At the base, `tests/test_codebase_hygiene_and_shims.py` held 16 tests in 349 lines. A search of `src`, `tests`, `docs` and `AGENTS.md` looked for the 11 deleted test names. The search also looked for `_DELETED_REVIEW_MODULES` and the `_imported_modules` helper of that file. It found them only in four task files and in that test file. The `_imported_modules` helper in `tests/test_test_module_independence.py` is a separate function. The `vulture` 2.16 trial ran on this tree through `uvx` and changed no file.

## Description
Eleven tests asserted that names deleted by earlier refactors stay deleted. Git history already records each deletion. Each later deletion refactor had to edit the same file. This change deletes the 11 tests, `_DELETED_REVIEW_MODULES`, the `_imported_modules` helper and the imports that only they used. The file keeps the three hardcoded-extension tests and `test_security_module_private_functions_all_have_callers`. The file name stays, because a later change that classifies files with a library replaces the extension tests.

- Deleted: `test_tool_has_no_func_alias`, `test_run_context_is_subclass_not_monkeypatched`, `test_no_native_mcp_toolset_alias`, `test_unused_sampling_model_and_os_access_classes_are_gone`, `test_devops_cli_error_has_no_code_alias`, `test_scan_app_has_no_shim_alias_commands`, `test_scan_module_has_no_legacy_variable_aliases`, `test_rag_app_has_no_reset_alias`, `test_the_model_verifier_its_catalog_and_its_guards_are_gone`, `test_syntopical_and_research_dead_settings_are_removed` and `test_vllm_dead_settings_commands_and_mcp_tools_are_removed`.
- The file shrinks from 349 to 90 lines.
- The plan for this item listed `test_run_context_instance_functionality` with the tombstones. It is not a tombstone, so it stays.
  - It is the only test that checks that `RunContext` stores `loaded_capability_ids` and `tool_call_metadata`.
  - It is also the only test that checks that `model_copy(update=...)` keeps the other fields.
  - It moved to `tests/test_pydantic_agent.py`, which already tests the helpers of `devops_cli/ai/agents/context.py`.
- No suppression marker was in the deleted lines, so no entry of `DEFAULT_SUPPRESSION_CEILINGS` falls. The swallowed-failure ceilings list `src` files only.
- Four older task files named a deleted test as a current test: `task-273`, `task-820`, `task-958` and `task-1150`. Each of those lines now says that #1871 deleted the test.

## Dead-code tool trial
The tool is `vulture` 2.16. Ruff has no rule for a function that nothing calls. Its unused-code rules cover imports, local variables, arguments and private type constructs only.

- At 100 percent confidence, `vulture src` reports 10 unused variables and no function.
- At 60 percent confidence, `vulture src` reports 1,777 findings.
  - 1,079 variables, 410 functions and 238 methods.
  - 34 attributes, 13 properties and 3 classes.
- With `tests` as a second source, a name that a test uses counts as used. Then 1,113 findings remain in `src`.
- 337 of the 1,113 findings are definitions that a framework registers with a decorator.
  - 235 Typer `command`, 47 `field_validator`, 15 FastMCP `resource` and 14 `model_validator`.
  - 10 Typer `callback`, 8 FastAPI `get` and 8 others.
  - Twelve `--ignore-decorators` patterns remove them.
- 55 more findings are called by name or through a table of strings.
  - 16 `on_*` and `action_*` handlers of Textual and FastMCP.
  - 6 `handle_*` methods of `HTMLParser` and `gidgethub`.
  - `model_post_init` of Pydantic and `convert_pre` of `markdownify`.
  - 31 helpers that `tests/conftest.py` calls from a table of strings.
  - Seven `--ignore-names` patterns remove them.
- The full output of the configured run has 720 findings in `src`.
  - 669 variables, 25 attributes, 14 methods and 12 functions.
  - 426 of the 694 variables and attributes are in `lang/en/` and `config/`. Code reads them through a lookup or does not read them.
  - 425 of the 694 names appear only once in `src` and `tests`.
  - The same run reports 346 more findings in `tests`.
- The functions-and-methods check has 26 findings: 12 functions and 14 methods.
  - `vulture` has no flag that selects findings by kind, so a gate row must filter the output.
  - 21 of the 26 names appear only at their definition in `src` and `tests`.
  - Two of the 21 are live framework hooks: `get_native_tools` and `get_description` in `src/devops_cli/ai/agents/capabilities.py:85` and `:89`.
  - `BaseCapability` extends the Pydantic AI `AbstractCapability`, and Pydantic AI calls both methods by name.
  - The other 19 are candidates for a follow-up. Each needs a manual check before anyone deletes it.
  - The other five findings share their name with another word in `src` or `tests`, such as a string, a comment or another object. They are `argo_app_status`, `set_mcp_sampling_model`, `to_cli`, `traces` and `merge`. They need a manual check too.
- The 19 candidates, with the line of each definition on this tree:
  - `run_stream_async` at `src/devops_cli/ai/agents/agent.py:1244`.
  - `validate_slot` at `src/devops_cli/ai/harness/slots.py:82`.
  - `_is_mutating_tool` at `src/devops_cli/ai/harness/slots.py:226`.
  - `validate_invariants` at `src/devops_cli/ai/harness/slots.py:748`.
  - `active_resources` at `src/devops_cli/ai/mcp/dispatcher.py:156`.
  - `record_rejection` at `src/devops_cli/ai/review/profile.py:203`.
  - `_unique_preserve_order` at `src/devops_cli/ai/review/sanitization.py:13`.
  - `_tokenize_title` at `src/devops_cli/ai/review_schema.py:148`.
  - `less_severe` at `src/devops_cli/ai/review_schema.py:624`.
  - `remove_custom_pricing` at `src/devops_cli/ai/spend/pricing.py:552`.
  - `should_ignore_dir` at `src/devops_cli/argo/gitops.py:68`.
  - `_extract_policy_include_email` at `src/devops_cli/cloudflare/client.py:219`.
  - `_run_gh_pr_command` at `src/devops_cli/commands/pr.py:98`.
  - `_resolve_pr_head_sha` at `src/devops_cli/commands/pr.py:320`.
  - `_render_logs_json` at `src/devops_cli/commands/sandbox.py:943`.
  - `_extract_roadmap_versions` at `src/devops_cli/docs/compactor.py:222`.
  - `get_last_request_epoch` at `src/devops_cli/github/rate_limiter.py:903`.
  - `_is_numbered` at `src/devops_cli/review/diff.py:68`.
  - `is_p1` at `src/devops_cli/roadmap/reprioritize.py:499`.
- `vulture` reports no function in `security/`, and the caller test finds no uncalled private function there. Both checks agree on this tree.
- A scratch module with an unused `_dead_helper` gets a `vulture` finding at 60 percent confidence. The caller test finds the same kind of function, in `security/` only.
- Decision: `vulture` is not adopted and the caller test stays.
  - The test has 29 lines. A whitelist for the full output holds about 720 entries, which is about 25 times as long.
  - The functions-and-methods check has only 26 findings, but it needs a configuration first. The configuration is 12 decorator patterns, 7 name patterns and a filter step.
  - Two of the 26 findings are live hooks, so the check reports false findings.
  - The patterns list framework names. A new framework decorator or hook adds a false finding until a person extends the list.
  - The name patterns also hide a dead function with a name such as `on_*`, `handle_*` or `reset_*`.
- Time: `vulture` takes 10 to 14 seconds over `src` and `tests`. The caller test takes 0.21 seconds.
- The rule "Open Tools Before Internal Code" asks for the written cost. The test is 29 lines, about 400 tokens to read (estimate). A `vulture` row with the full whitelist needs about 10,000 tokens to write (estimate). Many later changes also need a whitelist edit.

## Acceptance Criteria
- [x] The 11 tombstone tests are gone. A search of `src`, `tests`, `AGENTS.md` and `docs` outside `docs/agent/tasks` for their names finds nothing.
- [x] `test_run_context_instance_functionality` passes in `tests/test_pydantic_agent.py`.
- [x] The four tests that stay in `tests/test_codebase_hygiene_and_shims.py` pass.
- [x] These invariant test files pass too:
  - `tests/test_agent_task_files.py` and `tests/test_release_changelog_fragments.py`.
  - `tests/test_architectural_invariants.py` and `tests/test_swallowed_failures_ratchet.py`.
  - `tests/test_agents_md_claims.py` and `tests/test_docs_inventory.py`.
  - `tests/test_test_module_independence.py` and `tests/test_public_export_surface.py`.
- [x] `ruff check`, `ruff format --check`, `mypy` and `deptry` pass, and `uv run devops docs check` reports every file up to date.
- [x] The pull request records the `vulture` trial result and the decision.
- Pending a person: a person files the follow-up that checks the 19 candidates and deletes the dead ones.
- Pending a person: `uv run devops ci` passes on the delivering tree. This change ran the targeted tests, not the gate.
