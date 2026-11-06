# Tasks

## 1. Report a write option of a read-only tool and fix the tools

Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/ai/mcp/generator.py`, `tests/ai/mcp/test_path_confinement.py`, `tests/ai/mcp/test_mcp_tool_secrets.py`. Changes: `tests/ai/mcp/test_mcp_read_only_write_options.py` (new), `src/devops_cli/config/constants.py`, `src/devops_cli/ai/mcp/generator.py`.

- [x] 1.1 Write `tests/ai/mcp/test_mcp_read_only_write_options.py`. The cases of the rule run on a one-tool server. They cover a read-only tool with a writing option and each verb in each form. They cover a tool that is not read-only, a past form, and a word that only holds a verb. One test checks the published schema of every tool. One test checks the flag and the option of `pr_check_readiness`, `roadmap_refine`, `roadmap_run` and `ci`. One test checks that `scan_injection` and `tf_plan` stay read-only and publish no file option.
  - Verification: `uv run devops ci test tests/ai/mcp/test_mcp_read_only_write_options.py` fails on the base
- [x] 1.2 Set the `pr check-readiness`, `roadmap refine`, `roadmap run` and `ci` rows of `CONST_MCP_EXPOSURE_TABLE` to not read-only. Write a comment that names the writing option. Add the `("scan", "injection")` and `("tf", "plan")` entries to `_PATH_PARAM_RESTRICTIONS`. Each entry lists every option but the file option.
  - Verification: `uv run devops ci test tests/ai/mcp/test_mcp_read_only_write_options.py tests/invariants/test_dry_run_class_ratchet.py tests/ai/mcp/test_mcp.py tests/ai/mcp/test_fastmcp_contracts.py` passes

## 2. Regenerate the MCP tool reference

Reads: `docs/MCP_TOOLS.md`. Changes: `docs/MCP_TOOLS.md`.

- [x] 2.1 Run `uv run devops docs generate --sync-readme`. Four flags change. The `sarif` row of `scan_injection` and the `out` row of `tf_plan` go.
  - Verification: `uv run devops ci docs` passes

## Criteria

- A read-only tool publishes no option that writes: group 1
- A tool that keeps a writing option is not read-only: group 1
- A read-only tool publishes no option for a file that its command writes: group 1

## Workflow follow-up

- Issue #3642 owns the tools that write local state and that the class `no-external-request` keeps read-only. They are `ai_quiesce`, `ai_resume`, `ai_failover`, `ai_gateway_failover` and `review_export_feedback`.
- Issue #3644 owns the help text of `tf_notify_plan`, which says that the command posts a comment.
- Issue #3480 owns the path decision for `scan_injection.suppress` and `review_export_feedback.output`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
