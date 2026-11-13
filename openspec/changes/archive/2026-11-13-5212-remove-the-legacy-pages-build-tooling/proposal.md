# Proposal: #5212

## Why

#5183 moved the docs site from Jekyll to Zensical. The Pages source of the repository is GitHub Actions, and `.github/workflows/pages.yml` is the one deploy path. But some commands, text and tests still serve the legacy build from a branch source (#5212):

- `devops gh pages build` and the MCP tool `gh_pages_build` send `POST repos/{repo}/pages/builds`, which requests a build from the branch source.
- `devops gh pages builds` reads `GET repos/{repo}/pages/builds`. That list holds only the legacy builds, so the command shows an old history as the current history.
- `devops gh pages status` prints "Source Branch: main (path: /docs)" next to "Build Type: workflow", and `GitHubPagesInfo` invents the legacy values `legacy`, `main` and `/` when the API omits a field.
- Text teaches the legacy build or uses its terms, and a test refuses each YAML file in `docs/` as a guard against a Jekyll settings file.

The owner decided on 2026-11-12: "no need for old redirects, clean up legacy tooling and workflows and configs". Closes #5212.

## What Changes

- Delete `devops gh pages build`, `devops gh pages builds`, the MCP tool `gh_pages_build`, and their model, request functions, help texts and tests. A manual run of `pages.yml` (`workflow_dispatch`) replaces a manual build request.
- `GitHubPagesInfo` gives no value for `build_type`, `branch` and `path` when the API omits the field.
- `devops gh pages status` prints the source branch only for a `legacy` build. For a `workflow` build, it prints that a GitHub Actions workflow deploys the site.
- Remove "branch", "builds" and "build health" from the help texts and docstrings of the Pages commands and of the resource `resource://gh/pages/status`, and remove the fixed tool count from the docstring of `DomainGateMiddleware`.
- Correct the knowledge base, `docs/ROUTINE_TASKS.md`, `docs/DESIGN.md`, `docs/KNOWN_ISSUES.md` and `README.md`.
- Remove the `docs/*.y*ml` assertion and its Jekyll sentence from `test_the_repository_site_settings_pass_the_check`.
- Lower the swallowed-failures ceiling of `src/devops_cli/github/pages.py` from 2 to 1, and regenerate the reference documents and the MCP listing snapshot.
- The change has spec deltas, because a command, its output and an MCP tool are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-dry-run-class`: a new requirement for the request plans of `gh project`, `gh views` and `gh pages` counts eight commands, not ten, and its Pages scenario runs `devops gh pages status`. It replaces `gh-project-views-pages-request-plans`, because a MODIFIED block cannot drop the scenario of `devops gh pages build`.
- `github-pages`: the group `devops gh pages` holds `status` and `verify` only, and `status` shows the source branch only for a legacy build.

## Impact

- Code: `src/devops_cli/github/pages.py`, `src/devops_cli/commands/gh.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/ai/mcp/server.py`.
- Tests: `tests/github/test_github_pages.py`, `tests/commands/test_gh_cmd.py`, `tests/github/test_gh_project_views_pages_dry_run.py`, `tests/ai/mcp/test_mcp_tool_registry.py`, the MCP listing snapshot and `tests/fixtures/swallowed_failures_ceilings.json`.
- Documents: `src/devops_cli/ai/knowledge_base/devops_cli/tasks/github_project_management.md`, `docs/ROUTINE_TASKS.md`, `docs/DESIGN.md`, `docs/KNOWN_ISSUES.md`, `README.md`, and the generated `docs/MCP_TOOLS.md`, `docs/commands/gh.md` and `docs/CLI_REFERENCE.md`.
- A script that calls `devops gh pages build` or `builds`, or the MCP tool `gh_pages_build`, gets an unknown-command error. The project is alpha, so the change adds no alias.

## Weakened checks

- **`tests/github/test_github_pages.py::test_github_pages_build_info_model`**: Stopped: a change of the model `GitHubPagesBuildInfo`. Safeguard: the model is deleted, and `tests/commands/test_gh_cmd.py::test_the_pages_group_has_status_and_verify_only` fails when a build command returns.
- **`tests/github/test_github_pages.py::test_get_pages_builds_returns_history_records`**: Stopped: a change of the read of `/pages/builds`. Safeguard: the read is deleted, and the grep of acceptance criterion 2 of #5212 finds no caller.
- **`tests/github/test_github_pages.py::test_request_pages_build_triggers_deployment`**: Stopped: a change of the build request. Safeguard: the request is deleted, and `tests/ai/mcp/test_mcp_tool_registry.py::test_the_pages_tools_are_status_and_verify` and the listing snapshot fail when `gh_pages_build` returns.
- **`tests/commands/test_gh_cmd.py::test_gh_pages_builds`**: Stopped: a change of the output of `devops gh pages builds`. Safeguard: the command is deleted, and `tests/commands/test_gh_cmd.py::test_the_pages_group_has_status_and_verify_only` fails when it returns.
- **`tests/github/test_github_pages.py::test_the_repository_site_settings_pass_the_check`**: Stopped: a YAML file in `docs/`, which the assertion refused as a guard against a Jekyll settings file. Safeguard: the test keeps the check of `zensical.toml`. AGENTS.md rule 11 allows a guard only when an outside constraint blocks the fix, and no constraint applies. The glob also refused a correct `docs/.nav.yml`.

## Feasibility

Checked against `origin/main` 0fe31a67b on 2026-11-13. The issue took its evidence at 8fdeea033.

- `uv run devops gh api repos/dan-petty/devops-cli/pages --jq '{build_type, source, https_enforced}'` gives `{"build_type":"workflow","https_enforced":true,"source":{"branch":"main","path":"/docs"}}`. GitHub keeps `source` for a workflow build, but does not use it.
- `uv run devops gh api 'repos/dan-petty/devops-cli/pages/builds?per_page=1'` gives commit f4b1d73e9 at 2026-11-12T17:29:45Z, the last legacy build. `uv run devops gh api 'repos/dan-petty/devops-cli/actions/workflows/pages.yml/runs?branch=main&per_page=1'` gives head 0fe31a67b at 2026-11-12T23:51:25Z with `success`. So `/pages/builds` does not record the deploys of `pages.yml`.
- `.github/workflows/pages.yml` has `workflow_dispatch:`, so a manual run replaces a manual build request.
- `git grep` at 0fe31a67b finds each item of the issue: the build commands at `src/devops_cli/commands/gh.py:1080-1134`, the request functions at `src/devops_cli/github/pages.py:35-45,85-144`, the help texts at `src/devops_cli/lang/en/help.py:1298-1299`, the MCP row at `src/devops_cli/config/constants.py:356`, the docstrings at `src/devops_cli/ai/mcp/server.py:190,457-459`, and the texts in the knowledge base, `docs/ROUTINE_TASKS.md:142`, `docs/DESIGN.md:78`, `docs/KNOWN_ISSUES.md:34` and `README.md:40`. The line numbers moved after 8fdeea033, but each item is the same.
- The ADR item is done on `main`: #5270 put the line "2026-11-12: Fact out of date: the docs site builds with Zensical, not Jekyll (#5183)." in the `Status History` of ADR 0024. The ADR rules of `docs/adr/README.md` allow one dated line at the end of that section, and the line holds the fact. So this change does not change ADR 0024.
- A search of the repository for Jekyll, Liquid, `_config.yml`, `Gemfile`, `.nojekyll`, `pages-build-deployment` and `/pages/builds` outside the records (`CHANGELOG.md`, `docs/adr/`, `docs/agent/archive/`, `openspec/changes/archive/`, `tests/fixtures/`) finds only the items above. The workflows, the `Makefile`, the skills under `.agents/` and the configuration files hold no legacy Pages item.

## Existing Tool Considered

- The `workflow_dispatch` trigger of `.github/workflows/pages.yml` replaces `devops gh pages build`.
- The GitHub REST endpoints `actions/workflows/pages.yml/runs` and `deployments?environment=github-pages`, sent with `devops gh api`, replace `devops gh pages builds`.
- The change builds nothing, so it has no build cost. It deletes `GitHubPagesBuildInfo`, `_parse_single_build`, `pages_builds_args`, `pages_builds_requests`, `get_pages_builds`, `pages_build_args`, `pages_build_requests`, `request_pages_build`, `pages_builds_cmd` and `pages_build_cmd`.
