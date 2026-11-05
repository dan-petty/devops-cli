# Proposal

## Why

Issue #3235 reports that `CONST_MCP_EXPOSURE_TABLE` marks `pr_check_readiness` as read-only. The command has the option `--auto-resolve`, which resolves review threads on GitHub. A role server and a client choose tools by the read-only flag. So a model can get a write that the flag says it cannot make. No test finds this kind of error.

The check that the issue asks for finds three more tools of the same kind. `roadmap_refine` has `--confirm`, which writes the proposed designs to GitHub. `tf_plan` has `--out`, which writes the plan to a file. `scan_injection` has `--sarif`, which writes the findings to a file. All three are marked read-only.

## What Changes

- The `pr check-readiness`, `roadmap refine` and `tf plan` rows of `CONST_MCP_EXPOSURE_TABLE` in `src/devops_cli/config/constants.py` are not read-only. Each command keeps its option for people at the command line.
- `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` gets an entry for `("scan", "injection")` that leaves out `sarif`. The command prints its findings, so the model needs no file. The tool stays read-only, because the dry-run class of the command is `no-external-request`, and that class requires a read-only tool.
- A new test, `tests/ai/mcp/test_mcp_read_only_write_options.py`, reads the published schema of every tool. It fails on a read-only tool that has an option whose description holds `resolve`, `write`, `delete` or `create` in its base, `-s` or `-ing` form, and it names the tool and the option. A past form such as `resolved` does not count.
- `docs/MCP_TOOLS.md` is regenerated: four flags change and the `sarif` row of `scan_injection` goes.
- The change alters the flag and the schema that an MCP client reads, so it carries a spec delta and `skip_specs` is false.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `mcp-role-server`: A read-only tool publishes no option that writes, A tool that keeps a writing option is not read-only, The injection scan tool publishes no SARIF option

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/ai/mcp/generator.py`
- Documents: `docs/MCP_TOOLS.md`
- Tests: `tests/ai/mcp/test_mcp_read_only_write_options.py` (new)

## Feasibility

- Command output at `origin/main` commit 66a8a63e. A script that lists the published tools of `devops_cli.ai.mcp.server.mcp` shows `pr_check_readiness` with `readOnlyHint` true and the parameters `number`, `allow_draft`, `allow_pending_checks`, `allow_blocked_state`, `auto_resolve`, `allow_replied_threads`, `repo` and `dry_run`. The description of `auto_resolve` is "Automatically resolve review discussion threads that have received a reply from someone other than the thread opener." So the premise of the issue holds. The stage comment of 2026-11-02 on the issue says that the premise did not hold, but it gives no evidence.
- Command output, `uv run devops pr check-readiness --help`, lists `--auto-resolve`. The row in `src/devops_cli/config/constants.py` was `(("pr", "check-readiness"), 60.0, True, False)`.
- The same script, with the four verbs of the issue in the base, `-s` and `-ing` forms, finds four read-only options: `pr_check_readiness.auto_resolve`, `roadmap_refine.confirm`, `scan_injection.sarif` and `tf_plan.out`. With every form of the verbs, it also finds `roadmap_refine.item` (`wrote`), `sandbox_network_policy.public_whitelist` and `.local_whitelist` (`resolved`) and `scan_injection.suppress` (`resolved`). Each of these four describes a result, not a write. So the rule leaves out the past forms.
- When the `scan injection` row was set to not read-only, `tests/invariants/test_dry_run_class_ratchet.py::test_mcp_exposure_table_no_external_request_read_only` failed with "MCP tool for 'scan injection' has read_only=False but command is 'no-external-request'". The command prints its findings without `--sarif`, so the tool drops that option.
- `src/devops_cli/ai/mcp/generator.py` builds the description of a parameter from the help text of the Click option (`_build_parameter_field`), so the schema carries the same words as the help.

## Existing Tool Considered

No open, maintained tool covers the need. The alternatives check of 2026-11-05 on the issue found none: MCP security scanners validate annotation fields against each other or scan a running server, and none reads `CONST_MCP_EXPOSURE_TABLE` or the option help text of a CLI-derived tool. The change builds one repository-specific test. The written cost is about 30,000 tokens to build it, about 3,000 tokens per year to keep and fix it, and about two hours elapsed. The change deletes no internal code.
