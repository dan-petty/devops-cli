# Tasks

## 1. Show the source branch only for a legacy build

Kind: behavior. Reads: `src/devops_cli/github/pages.py`, `src/devops_cli/commands/gh.py`. Changes: `src/devops_cli/github/pages.py`, `src/devops_cli/commands/gh.py`, `tests/github/test_github_pages.py`, `tests/commands/test_gh_cmd.py`.

- [x] 1.1 Write `test_get_pages_status_gives_no_value_for_an_omitted_field`, and change `test_github_pages_info_model` and `test_get_pages_status_parses_status_payload` to a `workflow` build in `tests/github/test_github_pages.py`; change `test_gh_pages_status` to a `workflow` build that names the workflow and no source branch, and write `test_gh_pages_status_of_a_legacy_build_names_the_source_branch` in `tests/commands/test_gh_cmd.py`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Give `build_type`, `branch` and `path` of `GitHubPagesInfo` no default value, and print the source branch only for a `legacy` build in `devops gh pages status`
  - Verification: `$ uv run devops ci test tests/github/test_github_pages.py tests/commands/test_gh_cmd.py`

## 2. Delete the legacy build commands

Kind: behavior. Reads: `src/devops_cli/commands/gh.py`, `src/devops_cli/config/constants.py`. Changes: `src/devops_cli/github/pages.py`, `src/devops_cli/commands/gh.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/ai/mcp/server.py`, `tests/github/test_github_pages.py`, `tests/commands/test_gh_cmd.py`, `tests/github/test_gh_project_views_pages_dry_run.py`, `tests/ai/mcp/test_mcp_tool_registry.py`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`, `tests/fixtures/swallowed_failures_ceilings.json`, `docs/MCP_TOOLS.md`, `docs/commands/gh.md`, `docs/CLI_REFERENCE.md`.

- [x] 2.1 Write `test_the_pages_group_has_status_and_verify_only` in `tests/commands/test_gh_cmd.py` and `test_the_pages_tools_are_status_and_verify` in `tests/ai/mcp/test_mcp_tool_registry.py`, and remove `gh_pages_build` from the expected tools of that file
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 2.2 Delete `devops gh pages build`, `devops gh pages builds`, their model, request functions, help texts and tests, and the MCP row `("gh", "pages", "build")`; remove "branch", "builds" and "build health" from the Pages help texts and docstrings and the tool count from the docstring of `DomainGateMiddleware`; lower the swallowed-failures ceiling of `src/devops_cli/github/pages.py` with `--lower`; update the MCP listing snapshot and regenerate the documents
  - Verification: `$ uv run devops ci test tests/github/test_github_pages.py tests/commands/test_gh_cmd.py tests/github/test_gh_project_views_pages_dry_run.py tests/github/test_github_contract.py tests/ai/mcp tests/docs/test_docs_knowledge_base_argv.py`

## 3. Remove the YAML guard of docs/

Kind: other. Changes: `tests/github/test_github_pages.py`.

- [x] 3.1 Remove the `docs/*.y*ml` assertion and the Jekyll sentence of `test_the_repository_site_settings_pass_the_check`, and keep its check of `zensical.toml`
  - Verification: `$ uv run devops ci test tests/github/test_github_pages.py`

## 4. Correct the text

Kind: other. Changes: `src/devops_cli/ai/knowledge_base/devops_cli/tasks/github_project_management.md`, `docs/ROUTINE_TASKS.md`, `docs/DESIGN.md`, `docs/KNOWN_ISSUES.md`, `README.md`.

- [ ] 4.1 Replace the build commands of the knowledge base with a manual run of `pages.yml`, and remove "build history", "manual build dispatching", "publishing root", `enforce_https`, `gh_pages_build` and "build health" from it; correct `docs/ROUTINE_TASKS.md`, `docs/DESIGN.md`, `docs/KNOWN_ISSUES.md` and `README.md`
  - Verification: `$ uv run devops docs check`

## Criteria

- Group 2: `uv run devops gh pages --help` lists only `status` and `verify`.
- Group 2: `git grep -n -E 'pages_builds?\b|request_pages_build|get_pages_builds|GitHubPagesBuildInfo' -- src tests docs openspec/specs ':!docs/agent/archive'` finds nothing.
- Group 2: `uv run devops ci --check --only swallowed-failures` passes, and `tests/fixtures/swallowed_failures_ceilings.json` gives `src/devops_cli/github/pages.py` the ceiling 1.
- Group 2: after `uv run devops docs generate`, `git status --porcelain -- docs` is empty.
- Group 3: `git grep -n -i jekyll -- . ':!CHANGELOG.md' ':!openspec/changes/archive' ':!docs/adr' ':!docs/agent/archive' ':!tests/fixtures'` finds nothing.
- Group 4: `git grep -n -i -E 'publishing root|enforce_https|build health|build history|manual build dispatching' -- src docs ':!docs/agent/archive'` finds nothing, and `git grep -n -E '\{%-? ?(end)?raw' -- . ':!CHANGELOG.md' ':!openspec/changes/archive'` finds nothing.
- Pending a person: after the merge, `uv run devops gh pages status --repo dan-petty/devops-cli` prints "Build Type: workflow" and no "Source Branch" line, and the last run of `pages.yml` on `main` is `success`.

## Workflow follow-up

- #5154 reads the runs of `pages.yml` or the `github-pages` deployments for its Pages health step, not `/pages/builds`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
