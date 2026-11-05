# Proposal

## Why

Issue #3235 reports that `CONST_MCP_EXPOSURE_TABLE` marks `pr_check_readiness` as read-only. The command has the option `--auto-resolve`, which resolves review threads on GitHub. A role server and a client choose tools by the read-only flag. So a model can get a write that the flag says it cannot make. No test finds this kind of error.

The check that the issue asks for finds three more tools of the same kind. `roadmap_refine` has `--confirm`, which writes the proposed designs to GitHub. `scan_injection` has `--sarif`, which writes the findings to a file. `tf_plan` has `--out`, which writes the plan to a file. All three are marked read-only.

A read of the other options finds two more. `roadmap_run` has `--confirm`, which runs the same refine and intake jobs. `ci` has `--fix`, which is on by default and rewrites files. Both are marked read-only.

## What Changes

- The `pr check-readiness`, `roadmap refine`, `roadmap run` and `ci` rows of `CONST_MCP_EXPOSURE_TABLE` in `src/devops_cli/config/constants.py` are not read-only. Each command keeps its option for people at the command line.
- `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` gets an entry for `("scan", "injection")` that leaves out `sarif`. It gets an entry for `("tf", "plan")` that leaves out `out`. Each command prints its result, so the model needs no file. SECURITY.md rule 11 forbids a tool option for a path that the command writes. Both tools stay read-only.
- A new test, `tests/ai/mcp/test_mcp_read_only_write_options.py`, reads the published schema of every tool. It fails on a read-only tool that has an option whose description holds `resolve`, `write`, `delete` or `create`. The word is in its base, `-s` or `-ing` form. The test names the tool and the option. A past form such as `resolved` does not count.
- `docs/MCP_TOOLS.md` is regenerated. Four flags change. The `sarif` row of `scan_injection` and the `out` row of `tf_plan` go.
- The change alters the flag and the schema that an MCP client reads, so it carries a spec delta and `skip_specs` is false.
- The change fits one pull request.

Acceptance criterion 1 of the issue is met for the tools that the rule finds, and for `roadmap_run` and `ci`. Other tools stay open, and each has its own issue:

- `ai_quiesce`, `ai_resume`, `ai_failover`, `ai_gateway_failover` and `review_export_feedback` write local state or a file. Their commands have the class `no-external-request`. The requirement `mcp-read-only-hint-agrees-with-no-external-request` forces their flag to true. Issue #3642 owns that decision.
- `tf_notify_plan` posts nothing, so its flag is right. Its help says that it posts. Issue #3644 owns the text.
- `scan_injection.suppress` and `review_export_feedback.output` publish a path with no confinement decision. Issue #3480 owns both.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `mcp-role-server`: A read-only tool publishes no option that writes, A tool that keeps a writing option is not read-only, A read-only tool publishes no option for a file that its command writes

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/ai/mcp/generator.py`
- Documents: `docs/MCP_TOOLS.md`
- Tests: `tests/ai/mcp/test_mcp_read_only_write_options.py` (new)

## Feasibility

- Command output at `origin/main` commit 66a8a63e. A script that lists the published tools of `devops_cli.ai.mcp.server.mcp` shows `pr_check_readiness` with `readOnlyHint` true. Its parameters include `auto_resolve`. The description of `auto_resolve` is "Automatically resolve review discussion threads that have received a reply from someone other than the thread opener." So the premise of the issue holds. The stage comment of 2026-11-02 on the issue says that the premise did not hold, but it gives no evidence.
- Command output, `uv run devops pr check-readiness --help`, lists `--auto-resolve`. The row in `src/devops_cli/config/constants.py` was `(("pr", "check-readiness"), 60.0, True, False)`.
- The same script, with the four verbs of the issue in the base, `-s` and `-ing` forms, finds four read-only options. They are `pr_check_readiness.auto_resolve`, `roadmap_refine.confirm`, `scan_injection.sarif` and `tf_plan.out`.
- With every form of the verbs, the script also finds `roadmap_refine.item` (`wrote`), `sandbox_network_policy.public_whitelist` and `.local_whitelist` (`resolved`) and `scan_injection.suppress` (`resolved`). Each of these describes a result and not a write. So the rule leaves out the past forms.
- A read of the commands shows two more true writes. `devops ci` has `--fix/--no-fix` with the default true in `src/devops_cli/commands/ci.py`. `devops roadmap run --confirm` runs the intake and refine jobs. Both commands have the dry-run class `request-plan`, so the ratchet test accepts a flag that is not read-only.
- `devops tf notify-plan` in `src/devops_cli/commands/tf.py` sends no request. It puts the PR number in its payload and prints the comment. So `tf_notify_plan` is read-only, although its help says that it posts.
- When the `scan injection` row was set to not read-only, `tests/invariants/test_dry_run_class_ratchet.py::test_mcp_exposure_table_no_external_request_read_only` failed. The message was "MCP tool for 'scan injection' has read_only=False but command is 'no-external-request'". The command prints its findings without `--sarif`, so the tool drops that option.
- The generated tool `tf_plan` passed an absolute path outside the work tree to `--out` in the command line that it built. Nothing confined it. `PATH_CONFINEMENTS['tf_plan']` holds only `directory` and `var_file`. So the tool drops `out`.
- `src/devops_cli/ai/mcp/generator.py` builds the description of a parameter from the help text of the Click option (`_build_parameter_field`). So the schema carries the same words as the help.

## Existing Tool Considered

No open, maintained tool covers the need. The alternatives check of 2026-11-05 on the issue found none. MCP security scanners validate annotation fields against each other. Other scanners read a running server. None reads `CONST_MCP_EXPOSURE_TABLE` or the option help text of a CLI-derived tool. The change builds one repository-specific test. The written cost is about 30,000 tokens to build it. It is about 3,000 tokens per year to keep and fix it. The elapsed time is about two hours. The change deletes no internal code.
