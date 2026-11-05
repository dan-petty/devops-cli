# Proposal

## Why

Issue #3480 reports that the audit of the MCP path parameters finds a parameter by the words in its name. PR #3467 added the audit for #3300. It reads `_PATH_PARAM_KEYWORDS`: path, file, dir, dest, target, filename, filepath and uri. So a published option that holds a path under another name passes with no decision. A new tool with such an option passes too.

A census at `origin/main` finds eight published `Path` options with no decision: `ai_harness_offload.repo`, `ai_read.repo`, `docker_sandbox.workspace`, `sandbox_deploy.workspace`, `k8s_diff_helm.values`, `review_export_feedback.output`, `roadmap_refine.source` and `scan_injection.suppress`. PR #3649 (issue #3235) already removed `tf_plan.out` and `scan_injection.sarif`, the other two options of the issue. The string option `scan_sast.config` has no decision either. Its help says "a local path, or a registry id".

The risk is limited. No job role holds one of these tools, and the `ops` role is never served over the network. So the change is defense in depth.

## What Changes

- The audit in `tests/ai/mcp/test_path_confinement.py` finds a path parameter by its type and by its name. For a tool of the exposure table, the type is the Click type of the option: `typer.models.TyperPath` for a `Path` annotation, and `typer._click.types.File` for a `FileText` or `FileBinaryRead` annotation, which Typer opens from a path. For a tool that no command backs, the type is the `format: path` that pydantic writes for a `Path` annotation. A `Path` or file option under any name needs a decision. The test table `_TEXT_PATH_OPTIONS` names `scan_sast.config`, because a type check cannot find a string that holds a path.
- `PATH_CONFINEMENTS` in `src/devops_cli/ai/mcp/path_confinement.py` gets seven entries: `ai_harness_offload.repo`, `ai_read.repo`, `docker_sandbox.workspace`, `sandbox_deploy.workspace`, `k8s_diff_helm.values`, `roadmap_refine.source` and `scan_injection.suppress`. It also gets `scan_sast.config`.
- A new table `NOT_A_PATH_VALUE` in the same module names the values of a kept parameter that are not paths. A Semgrep registry id such as `p/default` is such a value for `scan_sast.config`. `confine_tool_paths` leaves it as it is, and confines every other value.
- `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` gets an entry for `("review", "export-feedback")` that leaves out `output`. The command appends to a dataset file, and nothing confines that file. The command keeps `--output` for a person.
- `_create_tool_function` runs `_check_path_confinement` before `_check_sandbox_preconditions`. The sandbox check then reads the resolved workspace, and the two sandbox tools refuse a workspace outside the work tree. `validate_sandbox_workspace` stays: it refuses sensitive directories inside the tree.
- Five tests that passed a path outside the work tree, or a relative path, get a work tree: `test_docker_sandbox_hands_its_command_over_after_the_options_end` and `test_roadmap_refine_contract_and_argv` in `tests/ai/mcp/test_fastmcp_contracts.py`, the Semgrep tool test in `tests/ai/mcp/test_mcp.py`, and `test_mcp_sandbox_tools_refuse_the_workspace_before_any_command_runs` and `test_fastmcp_sandbox_tools` in `tests/commands/test_sandbox_lifecycle.py`. The first of the two last tests loses its `run-user` case: `/run/user/1000` is outside every work tree, so the tool refuses it with a validation error before the sandbox check. The runner tests of the same file still cover that directory, and `test_a_sandbox_workspace_outside_the_work_tree_is_refused` covers the tool.
- `docs/MCP_TOOLS.md` is regenerated. The `output` row of `review_export_feedback` goes.
- `_PATH_PARAM_KEYWORDS` and `validate_path_parameter` do not change. Agent tools read the same list at run time through `src/devops_cli/ai/agents/context.py`. Tests pin the keyword names and show that no name of this change joins them.
- The change alters what an MCP client observes (published schema, refused values), so it carries a spec delta. It adds requirements to `mcp-tool-path-confinement` and changes one requirement of `agent-scan-tools`.
- The change does not touch a read-only flag. Issue #3642 owns the tools that write local state.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `mcp-tool-path-confinement`: The audit finds a path option by its type, A text option that holds a path has a named decision, A sandbox workspace is confined before the sandbox check, An option that writes a feedback dataset is not published, The runtime path check keeps its keywords
- `agent-scan-tools`: The MCP Semgrep tool uses the default ruleset unless the caller names one

## Impact

- Code: `src/devops_cli/ai/mcp/path_confinement.py`, `src/devops_cli/ai/mcp/generator.py`
- Documents: `docs/MCP_TOOLS.md` (generated)
- Tests: `tests/ai/mcp/test_path_confinement.py`, `tests/ai/mcp/test_fastmcp_contracts.py`, `tests/ai/mcp/test_mcp.py`, `tests/commands/test_sandbox_lifecycle.py`

## Feasibility

- Command output at `origin/main` commit f6d57ecd, with Typer 0.27.2 and Click 8.5.0. A script over `CONST_MCP_EXPOSURE_TABLE` compares the Click parameters of `resolve_click_command` with the published schema, `PATH_CONFINEMENTS` and `NOT_A_FILE_PATH`. It finds 59 published options whose Click type is `typer.models.TyperPath`. Fifty-one have a decision. The eight others are the options in Why. Over every option of the exposure table, published or not, 74 have that type and one has `typer._click.types.File`: `gh_issues_close.comment_file`, which `PATH_CONFINEMENTS` names. A `File` option is a path too, so the audit tests both types.
- `typer.models.TyperPath.__mro__` is `TyperPath`, `ParamType`, `object`. So `isinstance(param.type, click.Path)` is false, as the issue says, and the audit tests `isinstance(param.type, TyperPath)`.
- The same script with `typing.get_type_hints` of the command callback and an `os.PathLike` check finds the same 59 options. So the Click type and the annotation agree, and the audit needs no walker over annotations.
- The generator maps every Click type to a Python type (`_deduce_parameter_type`), so a generated tool shows `{"type": "string"}` for a path. A hand-written function with a `Path` annotation shows `format: path`. The test `test_the_audit_fails_on_a_path_annotation_of_a_tool_that_no_command_backs` reads that schema from a one-tool server.
- `src/devops_cli/sandbox/engine.py` (`validate_sandbox_workspace`, lines 203 to 218) refuses a symbolic link, the root, a forbidden system directory, the home directory, a path with the part `.ssh`, `.aws`, `.kube` or `.git`, and the socket directories. It does not test that the path is in the work tree. So the check is not enough alone. The order of the checks matters too. Before the change, the sandbox check ran first on the raw value, so a `../../etc` workspace raised `SandboxValidationError`. The failing run of the new test on the base shows that error.
- `semgrep scan --help` (Semgrep 1.179.0) says that `--config` takes "YAML configuration file, directory of YAML files ending in .yml|.yaml, URL of a configuration file, or Semgrep registry entry name", and `auto`. `devops scan sast` (`_registry_ruleset_for` in `src/devops_cli/commands/scan.py`) reads a registry id from the cache and gives any other value to Semgrep as it is. So a model that names a URL makes Semgrep fetch it. SECURITY.md rule 11 forbids that.
- The existing requirement "The MCP Semgrep tool uses the default ruleset unless the caller names one" says the second run names `./rules`. After the change it names the resolved path, so the requirement changes (MODIFIED).
- `src/devops_cli/security/suppression.py` (`load_policy`) resolves each `extends` parent from the policy file. So a policy file that a person keeps in the tree names its parents, and the tool writes no file.
- The failing run of `tests/ai/mcp/test_path_confinement.py` on the base shows 23 failures: the census and the audit for the eight options, the traversal cases, the sandbox cases and the Semgrep cases. The run after the change passes.

## Existing Tool Considered

The change uses what exists: the Click type that Typer builds (`typer.models.TyperPath`), the `format: path` of pydantic, `safe_resolve_subpath` and `confine_tool_paths` for a confined value, `validate_sandbox_workspace` for a sandbox mount and `is_registry_id` for a Semgrep registry id. No open, maintained library confines the path options of an MCP server, and none reads the Typer types of a CLI-derived tool. The change adds no dependency.

It builds one small table, `NOT_A_PATH_VALUE`, with one entry, and one audit in a test. The written cost is about 25,000 tokens to build, about 2,000 tokens per year to keep and fix, and about three hours elapsed. The change replaces the name-only audit of the test. It deletes no other internal code.
