# Design

## Context

Refine investigates an item with `investigate`, one pydantic-ai agent run with a set of tools. The alternatives job asks a different question of each item, so it needs a different set of tools, a different reply, and its own writes. The rest of the construction is the same: `get_task_model("analysis")`, `UsageLimits`, the streaming handler, the error mapping and one spend record.

## Decisions

- **One function for the run, two sets of tools.** `investigate` takes any object with a `tools()` method that returns pydantic-ai `Tool`s. `InvestigationTools` (refine) and `AlternativesTools` (this job) both do. The Firecrawl search body, with its URL bookkeeping, moves into one function, `cited_web_search`, that both tools call. Each tool set keeps its own search limit.
- **The tools hold the facts, the job writes the record.** `AlternativesTools` keeps the URLs that any tool returned (`allowed_urls`), the facts that the two fact tools read (`facts`, by URL), and the queries run. The reply cites URLs. The validation compares them with these sets after the run. The model does not write the tool's name, the license, the dates, `maintained` or the queries: the job knows them, so the model cannot get them wrong. The reply names the tool by `tool_url` only.
- **Validation after the run, not in the run.** The URL check needs the sets the run built. The check is on the reply after `investigate` returns, as refine's `validate_proposal` is. A refused reply skips the item. It is not tried again, because the same facts give the same refusal.
- **`maintained` is a function of facts.** `ToolFacts.maintained(now)` is true when the repository is not archived and its last activity is within 365 days. For a PyPI package, last activity is the upload time of its latest release. The window is a constant. A function of the time takes `now` as an argument, so a test sets the clock.
- **Facts through the store.** `RoadmapStore.repository_facts(owner/name)` is one new store operation with a GitHub adapter and an in-memory adapter, so the contract suite runs on both and the dry run lists its requests with the same argument builders. PyPI is read with `new_http_client` at `EgressLevel.PUBLIC`, as `devops survey` reads it.
- **The record block is a body block.** The block between the two markers holds the latest verdict and tool, so refine reads one block. The hash for "body changed since the check" ignores the job's block and the refine section, so neither job's own writes start a new check.
- **Write order.** For each item: the body block, then the job record, then the comment. A failure between two writes leaves a state that the next run repairs by a new check: a missing comment is the worst case, and the block and the record then still hold the verdict.
- **No label change, no close.** A covering tool is evidence for a person and for refine, not a decision.
- **Off when the check cannot search.** The check runs only for a public repository with a Firecrawl key (`web_search_of`, as refine uses it). Without a search, the verdict `none` would be false: it would say that no tool exists when no tool was looked for.

## Rejected alternatives

- **pydantic-ai `WebSearch` capability.** It needs a provider's native search or DuckDuckGo. The gateway's local models have no native search, and the owner chose Firecrawl. Rejected.
- **A second search provider (Tavily, DuckDuckGo).** Rejected for the same reason, and because `firecrawl_search` already counts each search in `devops_cli_firecrawl_searches_total`.
- **A new agent loop for the job.** `investigate` has the budget, streaming, error and spend handling that was fixed in #2379 and #2398. A second loop would repeat each fix. Rejected. The one change to `investigate` is its type: it takes a set of tools, not refine's class.
- **The model writes `maintained`, license and dates.** A model can state a fact that no tool returned. The job has the facts, so it writes them. Rejected.
- **A URL check in a pydantic-ai output validator.** The validator would retry the run on a made-up URL, and a retry costs model calls. The check after the run is the same rule at the cost of one run. Rejected.
- **A project-board field or a label for the verdict.** ADR 0016 keeps the board out of every job, and the owner chose that a person decides. The job record and the block hold the verdict. Rejected.
- **GraphQL for repository facts.** The roadmap spends GraphQL quota on other reads, and the REST repository and release reads give every needed field in two requests. Rejected.
