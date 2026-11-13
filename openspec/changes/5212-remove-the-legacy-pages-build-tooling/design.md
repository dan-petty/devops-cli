# Design

## Decisions

- **Delete the build commands with no alias**: the project is alpha, and AGENTS.md forbids a shim. A manual run of `pages.yml` and a read of its runs with `devops gh api` do the work of the two commands.
- **No invented values in `GitHubPagesInfo`**: `build_type`, `branch` and `path` are `None` when the API omits them. The field `build_type` stays, because the Pages health step of #5154 reads it.
- **Source line by build type**: `devops gh pages status` prints "Source Branch" only for `legacy`. For `workflow`, it prints "Source: a GitHub Actions workflow deploys the site". For a missing build type, it prints "Build Type: —" and no source line, because the command does not know the source.
- **No fixed tool count in the docstring**: the docstring of `DomainGateMiddleware` said 151 tools. The count was already wrong, and each change of the tool table changes it. The MCP listing snapshot holds the true list.
- **No change to ADR 0024**: #5270 added its `Status History` line for the move to Zensical. The body of an accepted record does not change.

## Rejected alternatives

- **Keep `devops gh pages builds` and read the runs of `pages.yml`**: the issue asks for no new command, and `devops gh api 'repos/{owner}/{repo}/actions/workflows/pages.yml/runs'` gives the history with the rate limiter. A short command for the deploy history is a separate item if a person asks for it.
- **Keep the `docs/*.y*ml` guard and allow `docs/.nav.yml`**: AGENTS.md rule 11 allows a guard only when an outside constraint blocks the fix. No constraint applies: `devops docs site build` reads `zensical.toml` only, and `test_verify_pages_configuration_reads_only_the_file_the_site_build_reads` proves it.
- **Add a redirect for the old page addresses**: the owner said on 2026-11-12 that the site needs no redirect, no file links to an old `*.html` address, and `zensical.toml` has no redirect plugin.
