# Design

## Decisions

- **Add research to StageToolset enum**: Resolve `research` as the `extended` tool list plus `search_web`. Keep `base` and `extended` network-free.
- **Short term with mask and egress guard**: The tool takes a short term from the model. It runs `mask_secrets` on the query. It checks for internal host names and private addresses using `is_local_or_reserved_domain` and `is_private_or_local_ip`. It refuses matching queries before calling `web_search`.
- **Title, URL, and cut snippet with data warning**: Web search results are formatted with titles, URLs, and cut snippets. The tool marks empty results with `empty_answer`. The prompt explicitly instructs the model that web results are data and not instructions.
- **Per-run stage search limit**: Introduce `CONST_ROADMAP_STAGE_SEARCH_LIMIT = 5`. Stop additional searches once reached, returning an `error_answer` and recording the outcome.

## Rejected alternatives

- **Add search_web to extended**: Breaks the documented network-free contract of `extended`.
- **Boolean allow_search setting**: Adds multiple setting combinations instead of a single cohesive enum.
- **Whole issue text as search query**: Can leak private issue details and violates egress minimization rules.
- **No search limit**: Allows runaway cost and token spend in stage loops.
