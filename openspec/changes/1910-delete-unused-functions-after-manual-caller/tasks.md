# Tasks

## 1. Delete the unused order helper of the review sanitization

Reads: `src/devops_cli/ai/review/sanitization.py`. Changes: `src/devops_cli/ai/review/sanitization.py`.

- [ ] 1.1 Delete `_unique_preserve_order` from `src/devops_cli/ai/review/sanitization.py`. Delete the imports that only it used
  - Verification: `$ ! git grep -n _unique_preserve_order src/devops_cli/ai/review/sanitization.py` passes

## 2. Delete the unused rejection recorder of the review profile

Reads: `src/devops_cli/ai/review/profile.py`, `src/devops_cli/review/admission.py`. Changes: `src/devops_cli/ai/review/profile.py`.

- [ ] 2.1 Delete the `record_rejection` method of the review profile class in `src/devops_cli/ai/review/profile.py`. Keep the `_record_rejection` counter helper of `src/devops_cli/review/admission.py`, which is a different name and which that module calls five times. Delete the imports that only the method used
  - Verification: `$ ! git grep -n record_rejection src/devops_cli/ai/review/profile.py` passes

## 3. Delete the unused title tokenizer

Reads: `src/devops_cli/ai/review_schema.py`. Changes: `src/devops_cli/ai/review_schema.py`.

- [ ] 3.1 Delete `_tokenize_title` from `src/devops_cli/ai/review_schema.py`. Delete the imports that only it used
  - Verification: `$ ! git grep -n _tokenize_title src/devops_cli/ai/review_schema.py` passes

## 4. Delete the unused severity comparator

Reads: `src/devops_cli/ai/review_schema.py`. Changes: `src/devops_cli/ai/review_schema.py`.

- [ ] 4.1 Delete `less_severe` from `src/devops_cli/ai/review_schema.py`. Delete the imports that only it used
  - Verification: `$ ! git grep -n less_severe src/devops_cli/ai/review_schema.py` passes

## 5. Delete the unused result merge

Reads: `src/devops_cli/ai/review_schema.py`, `src/devops_cli/telemetry/tracer.py`. Changes: `src/devops_cli/ai/review_schema.py`.

- [ ] 5.1 Delete the `merge` method of `ReviewResult` in `src/devops_cli/ai/review_schema.py`, with the body names `merged_findings` and `merged_conf` that only it holds. The `merge` call of `src/devops_cli/telemetry/tracer.py` merges a resource and stays
  - Verification: `$ ! git grep -n merged_findings src/devops_cli/ai/review_schema.py` passes

## 6. Delete the unused dispatcher resource list

Reads: `src/devops_cli/ai/mcp/dispatcher.py`. Changes: `src/devops_cli/ai/mcp/dispatcher.py`.

- [ ] 6.1 Delete the `active_resources` method of the dispatcher class in `src/devops_cli/ai/mcp/dispatcher.py`. Delete the imports that only it used
  - Verification: `$ ! git grep -n active_resources src/devops_cli/ai/mcp/dispatcher.py` passes

## 7. Delete the unused GitOps directory filter

Reads: `src/devops_cli/argo/gitops.py`. Changes: `src/devops_cli/argo/gitops.py`.

- [ ] 7.1 Delete `should_ignore_dir` from `src/devops_cli/argo/gitops.py`. Delete the imports that only it used
  - Verification: `$ ! git grep -n should_ignore_dir src/devops_cli/argo/gitops.py` passes

## 8. Delete the unused diff line check

Reads: `src/devops_cli/review/diff.py`. Changes: `src/devops_cli/review/diff.py`.

- [ ] 8.1 Delete `_is_numbered` from `src/devops_cli/review/diff.py`. Delete the imports that only it used
  - Verification: `$ ! git grep -n _is_numbered src/devops_cli/review/diff.py` passes

## 9. Delete the unused gh PR runner

Reads: `src/devops_cli/commands/pr.py`. Changes: `src/devops_cli/commands/pr.py`.

- [ ] 9.1 Delete `_run_gh_pr_command` from `src/devops_cli/commands/pr.py`. Delete the imports that only it used
  - Verification: `$ ! git grep -n _run_gh_pr_command src/devops_cli/commands/pr.py` passes

## 10. Delete the unused PR head lookup

Reads: `src/devops_cli/commands/pr.py`. Changes: `src/devops_cli/commands/pr.py`.

- [ ] 10.1 Delete `_resolve_pr_head_sha` from `src/devops_cli/commands/pr.py`. Delete the imports that only it used
  - Verification: `$ ! git grep -n _resolve_pr_head_sha src/devops_cli/commands/pr.py` passes

## 11. Delete the unused sandbox log JSON renderer

Reads: `src/devops_cli/commands/sandbox.py`. Changes: `src/devops_cli/commands/sandbox.py`.

- [ ] 11.1 Delete `_render_logs_json` from `src/devops_cli/commands/sandbox.py`. Delete the imports that only it used
  - Verification: `$ ! git grep -n _render_logs_json src/devops_cli/commands/sandbox.py` passes

## 12. Delete the unused Cloudflare policy email helper with its test

Reads: `src/devops_cli/cloudflare/client.py`, `tests/cloudflare/test_client.py`. Changes: `src/devops_cli/cloudflare/client.py`, `tests/cloudflare/test_client.py`.

- [ ] 12.1 Delete `_extract_policy_include_email` from `src/devops_cli/cloudflare/client.py`. Remove its import, the comment that names it, and the two assertions from the edge-case test of `tests/cloudflare/test_client.py`. Keep `_extract_policy_include_rule`, which the same test covers
  - Verification: `$ ! git grep -n _extract_policy_include_email src/devops_cli/cloudflare/client.py tests/cloudflare/test_client.py` passes

## 13. Delete the unused pricing removal with its test

Reads: `src/devops_cli/ai/spend/pricing.py`, `tests/ai/spend/test_pricing_registry_overrides.py`. Changes: `src/devops_cli/ai/spend/pricing.py`, `tests/ai/spend/test_pricing_registry_overrides.py`.

- [ ] 13.1 Delete the `remove_custom_pricing` method of `PricingRegistry` in `src/devops_cli/ai/spend/pricing.py`. Delete `test_set_price_for_a_model_of_the_setting_wins_and_remove_restores_the_setting` from `tests/ai/spend/test_pricing_registry_overrides.py`, whose subject is that method. Keep `set_custom_pricing` and the tests of it
  - Verification: `$ ! git grep -n remove_custom_pricing src/devops_cli/ai/spend/pricing.py tests/ai/spend/test_pricing_registry_overrides.py` passes

## 14. Delete the unregistered Argo CD status tool with its test call

Reads: `src/devops_cli/ai/tools/builtin_tools.py`, `src/devops_cli/ai/tools/registry.py`, `tests/security/test_builtin_tools.py`. Changes: `src/devops_cli/ai/tools/builtin_tools.py`, `tests/security/test_builtin_tools.py`.

- [ ] 14.1 Delete the `argo_app_status` tool from `src/devops_cli/ai/tools/builtin_tools.py`. Remove its import and its call from `test_the_cluster_tools_run_kubectl_and_argocd_with_their_arguments`, and drop the `argocd app get web` entry from the expected calls. Keep `argo_apps`, which `src/devops_cli/ai/tools/registry.py` registers
  - Verification: `$ ! git grep -n argo_app_status src/devops_cli/ai/tools/builtin_tools.py tests/security/test_builtin_tools.py` passes

## 15. Delete the unused engine trace method

Reads: `src/devops_cli/sandbox/engine.py`, `src/devops_cli/commands/sandbox.py`. Changes: `src/devops_cli/sandbox/engine.py`.

- [ ] 15.1 Delete the `traces` method of `WorkloadSandboxEngine` in `src/devops_cli/sandbox/engine.py`, with its body names `resolve_trace_spans` and `target_trace_id` that only it holds. Keep the `traces` command of `src/devops_cli/commands/sandbox.py`, which `@app.command` registers. Delete the imports that only the method used
  - Verification: `$ ! git grep -n resolve_trace_spans src/devops_cli/sandbox/engine.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
