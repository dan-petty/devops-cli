# Tasks

## 1. Report a write option of a read-only tool and fix the four tools

Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/ai/mcp/generator.py`, `tests/ai/mcp/test_path_confinement.py`, `tests/ai/mcp/test_mcp_tool_secrets.py`. Changes: `tests/ai/mcp/test_mcp_read_only_write_options.py` (new), `src/devops_cli/config/constants.py`, `src/devops_cli/ai/mcp/generator.py`.

- [x] 1.1 Write `tests/ai/mcp/test_mcp_read_only_write_options.py` with the cases of the rule on a one-tool server (a read-only tool with a writing option, each verb in each form, a tool that is not read-only, a past form, a word that only holds a verb), the check on the published schema of every tool, the flag and option of `pr_check_readiness`, `roadmap_refine` and `tf_plan`, and the schema of `scan_injection`
  - Verification: `uv run devops ci test tests/ai/mcp/test_mcp_read_only_write_options.py` fails on the base
- [x] 1.2 Set the `pr check-readiness`, `roadmap refine` and `tf plan` rows of `CONST_MCP_EXPOSURE_TABLE` to not read-only, with a comment that names the writing option. Add the `("scan", "injection")` entry to `_PATH_PARAM_RESTRICTIONS` with every option but `sarif`
  - Verification: `uv run devops ci test tests/ai/mcp/test_mcp_read_only_write_options.py tests/invariants/test_dry_run_class_ratchet.py tests/ai/mcp/test_mcp.py tests/ai/mcp/test_fastmcp_contracts.py` passes

## 2. Regenerate the MCP tool reference

Reads: `docs/MCP_TOOLS.md`. Changes: `docs/MCP_TOOLS.md`.

- [x] 2.1 Run `uv run devops docs generate --sync-readme`. The four flags change and the `sarif` row of `scan_injection` goes
  - Verification: `uv run devops ci docs` passes

## Criteria

- A read-only tool publishes no option that writes: group 1
- A tool that keeps a writing option is not read-only: group 1
- The injection scan tool publishes no SARIF option: group 1

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
