# Task: MCP Tools and Resources Call Commands and Options That Exist (#836)

**Issue**: [#836](https://github.com/dan-petty/devops-cli/issues/836)
**Status**: Done
**Milestone**: v0.2.24
**Priority**: priority/p0-critical
**Scope**: scope/mcp

## Description
`src/devops_cli/ai/mcp/server.py` built 169 `uv run devops` argv lists, and 12 of them failed on every call. None of these was a regression: each entry point was broken from the start. 22bba04 (v0.2.11) added ten of them: `scan_gitleaks`, `scan_semgrep` and `scan_checkov`, one day after 4cfe033 (v0.2.10) removed the scan aliases they call, plus `scan_complexity`, `k8s_chaos`, `k8s_audit`, `benchmark_embeddings`, `ai_architecture`, `resource://workspace/status` and `resource://argo/fleet/status`. b861fc4 (v0.2.13) added `benchmark_suite`. 4e48cd7 (v0.1.8) added the `--all` that `repos_sync` appends. A failure came back as ordinary tool text, not as an MCP error, and `tests/test_mcp.py` patched `_run_mcp_cmd` and asserted the mock's own return value, so nothing caught them.

`devops docs check` now resolves every argv list in the server against the real command tree, without running anything:

- `src/devops_cli/docs/command_resolver.py`: `resolve_devops_argv` walks from `main._COMMAND_SPECS` to each module app, as `main._delegate` does, and descends with `resolve_command`. It parses every node with `make_context(resilient_parsing=False)` and never calls `invoke`. A conversion error from a placeholder stops Click before its extra-argument check, so a lenient re-parse then recovers the leftovers. The vendored Click classes are duck-typed: a group is whatever has `resolve_command`, and an unknown option is the parse error that carries `possibilities`. The resolver reports only unknown commands, unknown options and unexpected extra arguments, and only for literal tokens. Code under `src/` can import it, so the prose, workflow and #697 checks can use it instead of writing a second walker.
- `src/devops_cli/docs/mcp_argv_collector.py`: an AST collector. It takes list literals that start with `uv run devops`, adds the literal flags appended or extended onto the same variable before that variable is reassigned, and replaces each non-literal element with a placeholder. `DocGenerator.check_docs` runs it, so both `devops docs check` and `devops docs generate --check` report each defect at its `path:line`.
- `module_click_command` builds each command module's Click tree once per process, and the docs generator and the resolver share it. Without the shared build, the check cost 0.90 to 1.09 s.

The 12 entry points:

| Entry point | Was | Now |
|---|---|---|
| `benchmark_embeddings` | `devops benchmark embeddings --model` | `devops ai benchmark --type embedding --models --samples` |
| `benchmark_suite` | `devops benchmark --suite` | `devops ai benchmark --suite` |
| `ai_architecture` | `devops analyze architecture` | deleted, with no shim |
| `scan_gitleaks`, `scan_semgrep`, `scan_checkov` | `devops scan gitleaks`, `semgrep`, `checkov` | `devops scan secrets`, `sast`, `iac` |
| `resource://workspace/status` | `devops workspace list` | `devops repos list`, the command the `workspace_list` tool already runs |
| `repos_sync` | `--all` (the `all_repos` parameter) | parameter dropped |
| `resource://argo/fleet/status` | `--json` | dropped |
| `scan_complexity` | `--max-nesting-depth` | `--max-indent` |
| `k8s_chaos` | positional `action`, `--experiment` | `experiment` is the positional; `dry_run` (default true) passes `--dry-run` |
| `k8s_audit` | `--namespace` | parameter dropped; `devops k8s audit` takes only `--dry-run` |

`k8s_chaos` called `action` "validate" by default. The command has no action argument, and without `--dry-run` it deletes a pod, so the tool previews by default and runs the experiment only when `dry_run` is false.

Key questions, answered as the issue proposed: `ai_architecture` returns, backed by the import graph, only when something needs it. The vulture step in `docs/ROADMAP.md:1040` is dropped, and the import-cycle part of that entry remains a separate item.

## Acceptance Criteria
- [x] `devops docs check` covers every literal argv list in the server and reports 0 unresolved commands and 0 unknown options. `test_every_mcp_server_argv_resolves` asserts at least 168 lists, all resolving. The count is 168, not the issue's 169, because this change deletes `ai_architecture`'s list. Run against the unfixed server, the same check listed exactly the 12 entry points above out of 169.
- [x] The fixture argv `uv run devops analyze architecture` is reported as unresolved, naming `analyze`: `test_unresolved_fixture_argv_are_reported_with_their_source_line` gives `fixture.py:2 ai_architecture: 'devops analyze architecture <target>': unknown command 'analyze' under 'devops'.`
- [x] A fixture with an unknown option is reported with its source line: the same test gives `fixture.py:6 ... unknown option '--max-nesting-depth' for 'devops scan complexity'` and `fixture.py:12 ... unknown option '--all' for 'devops repos sync'`. `test_docs_check_reports_an_unresolved_mcp_argv` shows `devops docs check` exiting 1 with that line.
- [x] No test in `tests/test_mcp.py` asserts a mocked return value for a changed or removed tool. Those assertions are gone. `test_repointed_mcp_entry_points_pass_real_command_lines` asserts the argv that each changed tool and resource hands `_run_mcp_cmd`, and `test_ai_architecture_tool_is_removed` asserts that the tool, its function and its export are gone. `tests/test_argo_fleet.py` asserts the argo resource's exact argv.
- [x] `uv run devops docs check` passes with the regenerated `docs/MCP_TOOLS.md`. README.md did not change.
- [x] The docs stage grows by at most 1 s. In-process, right after `generate_all_docs` has imported every command module, `check_mcp_server_argv` took 0.237, 0.259 and 0.269 s over three runs. End-to-end `check_docs` runs with and without the contract were within the noise of a parallel agent's gate runs, at 4.8 to 10.8 s either way.
- [x] No network access, no subprocess, no new dependency. `test_every_mcp_server_argv_resolves` and `test_resolving_parses_without_invoking_or_spawning` patch `subprocess.Popen` to fail, and assert that neither `_run_mcp_cmd` nor the `k8s chaos` experiment is called. The session fixture blocks external sockets, and `pyproject.toml` and `uv.lock` are unchanged.
- [x] The negative controls in `tests/test_docs_command_resolver.py` put a defect at each depth: root, group, leaf, the four-deep `argo cd apps list --json`, the group-as-command `ai benchmark`, and the root-level `lint`. Another control checks that a placeholder the integer option rejects still lets a stray argument be found. A Typer upgrade that changes the walk turns these findings into `None`, and a renamed `_protected_args` raises.
- [x] `uv run devops ci` passes.
