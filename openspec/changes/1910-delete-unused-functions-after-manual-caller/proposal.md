# Proposal

## Why

The vulture trial of #1871 listed 19 symbols in `src` that appear only at their definition. Each may be dead code, and dead code that no caller reaches still costs a reader, a test and a type check. #1910 deletes the ones that have no production caller.

## What Changes

- Delete `_unique_preserve_order` from `src/devops_cli/ai/review/sanitization.py`, where the name has one line in the tree: its definition.
- Delete the `record_rejection` method from `src/devops_cli/ai/review/profile.py`, and keep the separate `_record_rejection` counter helper, which is a different name and is live.
- Delete `_tokenize_title`, `less_severe` and the `merge` method of `ReviewResult` from `src/devops_cli/ai/review_schema.py`.
- Delete `active_resources` from `src/devops_cli/ai/mcp/dispatcher.py`, `should_ignore_dir` from `src/devops_cli/argo/gitops.py` and `_is_numbered` from `src/devops_cli/review/diff.py`.
- Delete `_run_gh_pr_command` and `_resolve_pr_head_sha` from `src/devops_cli/commands/pr.py`, and `_render_logs_json` from `src/devops_cli/commands/sandbox.py`.
- Delete `_extract_policy_include_email` from `src/devops_cli/cloudflare/client.py` with its import, its comment and its two assertions in `tests/cloudflare/test_client.py`.
- Delete `PricingRegistry.remove_custom_pricing` from `src/devops_cli/ai/spend/pricing.py` with `test_set_price_for_a_model_of_the_setting_wins_and_remove_restores_the_setting`.
- Delete `argo_app_status` from `src/devops_cli/ai/tools/builtin_tools.py` with its import and its call in `test_the_cluster_tools_run_kubectl_and_argocd_with_their_arguments`, and keep `argo_apps`, which the registry registers.
- Delete the `traces` method of `WorkloadSandboxEngine` from `src/devops_cli/sandbox/engine.py`, and keep the `traces` command of `src/devops_cli/commands/sandbox.py`.
- Leave the harness slot helpers and the rate limiter module unchanged, because the refine block of #1910 reserves them for the items that delete those modules.
- Add no vulture gate: the trial needed 12 decorator patterns and 7 name patterns, and vulture cannot see a framework hook or a registry entry.
- Carry no spec delta: the change deletes uncalled code and changes no command, option, message or service behavior, so no capability gains a requirement.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/review/sanitization.py`, `src/devops_cli/ai/review/profile.py`, `src/devops_cli/ai/review_schema.py`, `src/devops_cli/ai/mcp/dispatcher.py`, `src/devops_cli/argo/gitops.py`, `src/devops_cli/review/diff.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/commands/sandbox.py`, `src/devops_cli/cloudflare/client.py`, `src/devops_cli/ai/spend/pricing.py`, `src/devops_cli/ai/tools/builtin_tools.py`, `src/devops_cli/sandbox/engine.py`
- Tests: `tests/cloudflare/test_client.py`, `tests/ai/spend/test_pricing_registry_overrides.py`, `tests/security/test_builtin_tools.py`

## Feasibility

- The probes confirm the files that the plan changes: "The path `src/devops_cli/ai/mcp/dispatcher.py` is a file of the staging commit.", "The path `src/devops_cli/ai/review/profile.py` is a file of the staging commit." and "The path `src/devops_cli/ai/review_schema.py` is a file of the staging commit."
- The probes show one cited file is gone: "The path `src/devops_cli/ai/agents/agent.py` is no file of the staging commit." The line "Commit 5edd7a547 2026-11-09 refactor(ai): replace PydanticAgent with pydantic-ai Agent (#4237) deleted or renamed it." shows that `run_stream_async` left with it.
- The probes also show the task document of #1871 is gone: "The path `docs/agent/tasks/task-1871-tombstone-tests-and-dead-code-tool.md` is no file of the staging commit."
- list_files("src/devops_cli/docs") returned `src/devops_cli/docs/__init__.py`, `src/devops_cli/docs/generator.py`, `src/devops_cli/docs/inventory.py`, `src/devops_cli/docs/markdown_argv_collector.py` and `src/devops_cli/docs/source_argv_collector.py`, so the module of `_extract_roadmap_versions` is gone; list_files("src/devops_cli/roadmap") holds no reprioritize module, so `is_p1` is gone too.
- search_code("active_resources") returned one line, `src/devops_cli/ai/mcp/dispatcher.py:def active_resources`, so the method has no caller in any file of the commit.
- search_code("record_rejection") returned the definition in `src/devops_cli/ai/review/profile.py` and five lines of `_record_rejection` in `src/devops_cli/review/admission.py`, which is a different and live name: `src/devops_cli/review/admission.py:108:_record_rejection(rejection_counts, "no-anchor")`.
- search_code("_unique_preserve_order") returned one line, `src/devops_cli/ai/review/sanitization.py:def _unique_preserve_order`.
- search_code("_tokenize_title") returned one line, `src/devops_cli/ai/review_schema.py:def _tokenize_title`, and search_code("less_severe") returned one line, `src/devops_cli/ai/review_schema.py:def less_severe`.
- search_code("def merge(") returned one line, `src/devops_cli/ai/review_schema.py:1143:def merge(self, other: ReviewResult) -> ReviewResult:`, and search_code(".merge(") returned only `src/devops_cli/telemetry/tracer.py:1067:).merge(OTELResourceDetector().detect())`, which merges a resource and not a `ReviewResult`.
- search_code("merged_findings") returned three lines, `src/devops_cli/ai/review_schema.py:1145:merged_findings = sort_findings(self.findings + other.findings)` and the two lines after it, all inside the body of the method, so the verify of the merge group finds nothing once the method is gone.
- search_code("remove_custom_pricing") returned the definition in `src/devops_cli/ai/spend/pricing.py` and one test line, so a test is its only caller.
- search_code("should_ignore_dir") returned one line, `src/devops_cli/argo/gitops.py:def should_ignore_dir`.
- search_code("_extract_policy_include_email") returned five lines: the definition in `src/devops_cli/cloudflare/client.py`, the import at `tests/cloudflare/test_client.py:20:_extract_policy_include_email,`, the comment at line 841 and the assertions at `tests/cloudflare/test_client.py:853:assert _extract_policy_include_email({"email": "u@example.com"}) == {"email": "u@example.com"}` and line 854.
- search_code("_run_gh_pr_command") returned one line, `src/devops_cli/commands/pr.py:def _run_gh_pr_command`, and search_code("_resolve_pr_head_sha") returned one line, `src/devops_cli/commands/pr.py:def _resolve_pr_head_sha`.
- search_code("_render_logs_json") returned one line, `src/devops_cli/commands/sandbox.py:def _render_logs_json`.
- search_code("_is_numbered") returned two lines: `src/devops_cli/review/diff.py:68:def _is_numbered(line: str) -> bool:` and `tests/ai/mcp/test_mcp_argument_refusal.py:77:async def test_each_violation_is_numbered_with_its_parameter_and_kind(`, a test whose name ends with that text and which calls nothing.
- search_code("argo_app_status") returned 22 lines. The definition is `src/devops_cli/ai/tools/builtin_tools.py:def argo_app_status`, and the other lines name `format_argo_app_status_panel` or the string `name="argo_app_status"` of `src/devops_cli/commands/argo.py`.
- search_code("def traces(") returned `src/devops_cli/commands/sandbox.py:823:def traces(`, which carries `@app.command("traces")` and stays, and `src/devops_cli/sandbox/engine.py:618:def traces(`; search_code(".traces(") returned no match, so no line calls the method.
- search_code("resolve_trace_spans") returned `src/devops_cli/sandbox/engine.py:626:from devops_cli.telemetry.waterfall import resolve_trace_spans` and `src/devops_cli/sandbox/engine.py:637:return resolve_trace_spans(trace_id=target_trace_id, tempo_url=tempo_url)`, both inside the method, so the verify of the traces group finds nothing once the method is gone.
- search_code("set_mcp_sampling_model") and search_code("to_cli") returned only `CHANGELOG.md`, an archived change folder and eval fixtures, so neither name has a definition in `src` at the staging commit.
- search_code returned one line each for `validate_slot`, `_is_mutating_tool`, `validate_invariants` and `get_last_request_epoch`, the definitions in `src/devops_cli/ai/harness/slots.py` and `src/devops_cli/github/rate_limiter.py`; the refine block requires both files unchanged, so the plan allowlists them.
- find_issues("rate_limiter") answered that no open item names it, and find_issues("harness slots") listed #1910 and #4405; whether another open item deletes those two modules is `not checked`.
- The issue names `get_native_tools` and `get_description` as live Pydantic AI hooks; this run did not check them, so the plan changes nothing there.
- The 19 members of the issue's list are each decided: 12 are deleted, 3 left with deleted modules (`run_stream_async`, `_extract_roadmap_versions`, `is_p1`), and 4 are allowlisted. Of the five names that share a word, 3 are deleted and 2 have no definition in `src`.
- The plan calls no function that needs a checkout, a client or a network; each verify calls `git grep`, which needs a checkout of the repository and no network.
- Each verify program is `git grep`, which is in the runner image and not `NOT_IN_RUNNER`; the pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, all capabilities dropped and the `RuntimeDefault` seccomp profile, and `git grep` writes nothing.
- A verify that still finds a deleted name exits 1 and takes failure class `lint` with action `repair`; a failing test takes class `test` with action `repair`, and a failing mypy takes class `types` with action `repair`.
- The pull request runs the full suite and mypy through the required checks `Tests & Coverage` and `Static Analysis`, and the change adds no workflow.

## Existing Tool Considered

vulture (https://github.com/jendrikseipp/vulture) is the open, maintained dead-code finder that produced the candidate list. It cannot see a framework hook, a registry entry or a string caller, so the change reads each caller by hand and adds no gate.

## Dependencies

None.
