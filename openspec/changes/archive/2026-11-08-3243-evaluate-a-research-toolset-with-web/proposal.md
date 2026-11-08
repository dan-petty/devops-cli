# Proposal: #3243

## Why

The stage toolbox omits `search_web` by design. It makes no network call. But rule 3 of AGENTS.md asks the planner to consider existing tools. Reviews show that planners without web search cannot evaluate open-source alternatives. This change adds the `research` toolset to `roadmap.stage.toolset`. The `research` set provides `extended` tools plus guarded `search_web`.

Closes #3243.

## What Changes

- Add `research` to `StageToolset` in `src/devops_cli/config/defaults.py` and settings.
- Add `HOLDER_STAGE_RESEARCH` to `src/devops_cli/roadmap/tools.py`.
- Add `search_web` to `StageTools` in `src/devops_cli/roadmap/stage/stage_tools.py`.
- Apply secret masking and private-data guards before web searches leave the process.
- Refuse queries with internal hosts or private addresses before any search provider call.
- Cut search results and frame result text as data, not instructions.
- Add a per-run stage search limit constant and count searches by outcome.
- Add `roadmap_stage_tools_research.md` task prompt and include it in `prompt_version`.

## Capabilities

- `roadmap-stage`: Add `research` toolset with guarded `search_web` tool and per-run search limits.

## Impact

- The stage planner can search the web for alternatives when configured with `toolset: research`.
- Default behavior stays `extended`, keeping stage runs network-free by default.
- No secrets, internal host names, or private addresses leave the Service during web searches.

## Feasibility

- The `web_search` engine exists at `src/devops_cli/ai/web_search.py`.
- The secret masker exists at `src/devops_cli/security/sanitizer.py`.
- The private-address checks exist at `src/devops_cli/security/reference_extractor.py`.
- The stage toolbox already routes tool sets via `StageTools.tools()`.

## Existing Tool Considered

The repository already uses Firecrawl, SearXNG, and DuckDuckGo through `src/devops_cli/ai/web_search.py`. This change uses that existing search infrastructure. It adds the required stage glue, guardrails, and telemetry without introducing a new search engine.
