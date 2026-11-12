# Design

## Decisions

- **Delete a symbol when its tests exist to test that symbol.**: No module of `src`, no entry point, no framework hook, no document and no string calls it, so docs/TESTING.md makes it dead code. The tests whose subject is the symbol go with it.
- **Keep a symbol that tests use only to observe other live code.**: Such a symbol is a test seam, as `wait_active` is. Without it, a test must read private state. The issue names `wait_active` as a false positive for this reason.
- **Move a test of live behaviour from a deleted wrapper to the live function.**: The wrapper adds nothing, and the test keeps its coverage. Examples: `_tally_findings` to `tally_findings`, `_apply_symbol_delta_to_meta` to `apply_branch_symbol_delta`, `is_on_merged_code` to `why_not_on_merged_code`, `prewarm_async` to `preload_models`, and the three format readers to `_extract_structured_strings`.
- **Delete a whole module when no module of `src` imports it.**: `ai/agents/capabilities.py` stayed after #4237 replaced the agent, and `k8s/chaos_runner.py` and `output/table_builder.py` have no importer.
- **Delete what only a deleted symbol used.**: A second vulture run after the first deletions listed the orphans: helpers, classes, constants, defaults and one tool message. The change deletes them in the same files.
- **Leave the files that another open item changes.**: An edit there conflicts with that item.
- **Add no vulture gate to CI.**: The trial of #1871 needed 12 decorator patterns and 7 name patterns, and vulture cannot see dynamic use.
- **Carry no spec delta.**: The change deletes code that no command, option, message or service reaches.

## The 54 audit symbols that stay

- Framework hook: `tool_plain` (overrides pydantic-ai `FunctionToolset.tool_plain`), `on_start` and `on_end` (OpenTelemetry `SpanProcessor`), `on_unmount` (Textual).
- Invariant or gate helper: `named_job_tools`, `resolve_step_rows`, `resolve_scan_report_scanners`, `import_cycle_violations`, `interface_layer_violations`, `document_class`, `is_pattern_entry`, `discover_path_applications`, `check_argocd_gate`, `keyring_only_keys`, `current_genai_names`.
- Test seam: `_create_http_client` (egress tests build a client), `chat_stream` (the single-turn stream entry of the stream tests), `parse_junit_xml` (a shard test reads its report), `get_state` and `get_cached_resources` (the only readers of the informer cache), `register_instance` (the `register_sandbox` fixture), `get_cache_stats`, `wait_active`, `export_prometheus_text`, `pending_domains`, `failed_domains`.
- New code that is not wired yet: the six `RepoRef` builders of #4612, and `build_allowlist` and `check_command` of #4004.
- A file that another open item changes: the ten methods of `ai/harness/slots.py` and three methods of `github/rate_limiter.py` (the refine block of #1910), `evaluate_model` (`ai/benchmark/embedding_runner.py`, #1928), `add_link` and `extract_trace_context` (`telemetry/tracer.py`, #4697).
- A name that a spec or a standards document holds: `_parse_and_validate_scheme` (spec `configured-service-urls`), `can_transition` (spec `review-finding-state`), `run_json_subprocess` (docs/SDLC.md and docs/ROUTINE_TASKS.md).
- A reader that a contract table drives: `_read_event_stream`. No provider reads a server-sent event stream with it, but the stream contract tests drive it and the NDJSON reader through one table of ten tests.

## The names of the issue list

- Deleted: `_unique_preserve_order`, `record_rejection`, `_tokenize_title`, `less_severe`, `ReviewResult.merge`, `active_resources`, `should_ignore_dir`, `_is_numbered`, `_render_logs_json`, `_extract_policy_include_email`, `remove_custom_pricing`, `argo_app_status` and `WorkloadSandboxEngine.traces`.
- Kept: `validate_slot`, `_is_mutating_tool`, `validate_invariants` and `get_last_request_epoch` (refine block), and `_run_gh_pr_command` and `_resolve_pr_head_sha`, because the deletion of `devops pr update` changes `commands/pr.py` now.
- Gone before this change: `run_stream_async`, `_extract_roadmap_versions`, `is_p1`, `set_mcp_sampling_model` and `to_cli`.

## Rejected alternatives

- **Delete every symbol that vulture lists.**: `is_pattern_entry` serves the docs inventory invariant, `parse_junit_xml` reads a shard report in a test, and the hooks are called by a framework. Vulture sees none of these callers.
- **Delete the 15 names of the staged plan only.**: The CI audit set the 129-symbol list as the scope of #1910.
- **Delete the server-sent event reader now.**: Its ten contract tests share one table with the NDJSON reader, so the deletion is a test rewrite of its own.
- **Delete the two spec-named functions with a spec delta.**: A REMOVED or MODIFIED requirement changes a spec that a person reviewed. A follow-up item decides it.
- **Parse the shard JUnit report with `xml.etree` in the test.**: No test parses XML today, and the security scans flag `xml.etree`.
- **Add vulture as a CI row.**: The trial needed 12 decorator patterns and 7 name patterns before its list was usable.
