# Proposal: #4672

## Why
The owner asked on 2026-11-11 for an open search that finds good reference implementations for each issue and links them in the issue (#4672). Today no issue links one. The alternatives check keeps at most 5 sources as comment text, and 93 of 330 checks are skip classes with no search. The owner decision of 2026-11-13 extends the step to official documentation, behind a domain allowlist, and keeps it in mode `plan` until #6588.

## What Changes
- A reference step runs after the verdict of each checked item, also for a skip class. It makes no model call of its own. Its queries are the rule queries of the item body (import statements, package names of URLs, code spans) and at most 3 `reference_queries` of the same model reply.
- Providers are data. `github-code` (`GET /search/code`) and `github-repository` (`GET /search/repositories`) go through the roadmap store on the paced GitHub session. `mcp-code` is an optional provider on the MCP server of `roadmap.alternatives.references_mcp_url`, through `RoadmapMcpToolset` in a new optional mode. A server that is down at the start leaves the run. A private repository gets the two GitHub providers only.
- The gates and the rank are code. The step verifies each permalink with `repository_file` at the head commit, renders it with `render_permalink`, and keeps at most 3. A documentation link needs a host on `CONST_ROADMAP_ALTERNATIVES_REFERENCE_DOC_DOMAINS` and a page that answers 200.
- The setting `roadmap.alternatives.references` holds `off`, `plan` or `on`, and is `plan` by default. Mode `plan` writes the verified links to the log and counts them. Mode `on` writes them in the block, in the comment and in `alternatives.refs`.
- The step has the bounds of 3 code searches, 15 fact reads and 120 s for one item, and it fails soft.
- The decision point `brain.reference_relevance` is registered and runs in `shadow` only. The counter `devops_cli_brain_references_total{provider,result}` counts each search and each link.
- The roadmap store reads the code search, the repository search, the reference facts of a repository in one GraphQL read, and a file of another repository.
- The change adds behavior that a consumer observes (a setting, a block text, a job record key, a metric), so it has a spec delta. The block line of a skip class changes from `no search` to `no model call`.

## Capabilities
- `roadmap-alternatives`: 11 added requirements for the reference step, and the requirement of the skip class modified. The inventory requirements stay in force.

## Impact
- A run of the alternatives check sends, for each item, at most 3 requests to GitHub's code search and at most 15 other reads (GitHub, deps.dev, a documentation host). The code search quota of GitHub is 10 requests a minute.
- With the default mode `plan`, no issue text and no job record changes. The result line of the job gets the count `references`.
- The cluster ConfigMap needs no change for mode `plan`. The switch to `on` is #6588.
- No new dependency.
- The change fits one pull request.
- Internal code that the change deletes: none.

## Feasibility
- `GET /search/code` and `GET /search/repositories` answered a probe with the session token on 2026-11-26 (`devops gh api 'search/code?q=...&per_page=2'`, `total_count` 110720). A code search item holds `path` and `repository.full_name`, `repository.private`.
- A repository search with several `repo:` qualifiers gives each named repository: `q=repo:pydantic/pydantic-ai repo:astral-sh/uv repo:fastapi/typer fork:true` gave `total_count` 3 on 2026-11-26. So one request gives the facts of all code hits.
- One GraphQL read gives `isPrivate`, `isArchived`, `isFork`, `pushedAt`, `stargazerCount`, `licenseInfo.spdxId`, `defaultBranchRef.target.oid` and the object at `HEAD:tests` (probe of 2026-11-26 on `pydantic/pydantic-ai`).
- `render_permalink` (`src/devops_cli/citation.py:207`) gives the form `https://github.com/<owner>/<repo>/blob/<sha>/<path>#L<a>-L<b>`, and `repository_file` raises `GitHubFileNotFoundError` on a 404.
- `MCPToolset` of pydantic-ai 2.75.0 takes an `http_client` and has `direct_call_tool`. A test sends the connection of the provider through `devops_cli.http.entry`, and a refused connection gives `RoadmapMcpUnavailableError`.
- The deps.dev API documents `GET /v3alpha/systems/{system}/packages/{name}/versions/{version}:dependents` with `directDependentCount` (docs.deps.dev/api/v3alpha, read 2026-11-26). No request went to deps.dev or to grep.app: the first live read is the proof of mode `plan` after the release.
- The living spec holds 68 requirements, and the limit is 80. The delta adds 11.

## Existing Tool Considered
sudosubin/grep-app-cli (`https://github.com/sudosubin/grep-app-cli`), MIT, maintained, and the grep.app MCP server (`https://mcp.grep.app`). The alternatives check of 2026-11-23 gave the verdict `partly`: grep.app finds code hits, and it has no gates, no rank, no permalink check, no documentation allowlist and no issue writing. grep.app publishes no terms and no rate limits. So it is the optional provider `mcp-code` for a public repository, through the MCP client of pydantic-ai that the project already has, and GitHub's code search is the default. The project builds the rest at the written cost of about 250,000 tokens and 5 hours (#4672). deps.dev gives the dependents and the linked packages, and `packaging` reads the versions.
