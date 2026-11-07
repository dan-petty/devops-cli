# Design

## Decisions

- **One `PageFetch` object for both jobs.**: The guards, the limit, the frame and the counter are the same in refine and in the check. Each toolset holds one object and its tool method calls `fetch`. The `toolset` label tells the two apart.
- **The tool is on when a `PageFetch` is given.**: The round builds it from `WebSearch.fetch`, which is true when web search is on and `crawl4ai.url` is set. A tool class with no `PageFetch` has no `fetch_page`, so `StageTools` needs no change.
- **A URL is fetchable when a search returned it in this run, or the item text names it.**: `offer` takes the URLs of each `search_web` answer. `named_urls` reads the title and the body of the item with `CONST_URL_CANDIDATE_RE`. A URL compares after `normalize_url`, so a trailing slash does not make another URL. The title and the snippet of a hit are never copied: only the URL stays.
- **https only, checked in the tool.**: The owner approved https only. `fetch_page_text` accepts http too, and a change of that rule would change its other callers.
- **The limit is 3 fetches for each run, and a failed fetch uses one.**: A refused URL uses none, because no request was sent. A failed fetch reached the service, so it costs as one. A page is cut at 8000 characters, as other tool answers are.
- **A failure is an answer.**: `InvalidURLError` and `SSRFBlockedError` give "not on a public web host". Any other error of the client gives "The page fetch failed" with the reason of `PageTextError` or the class of the error. The reason holds no token and no page URL.
- **The frame names the source and the date, and the fence follows the text.**: The model must cite them. `code_fence` makes a fence longer than any run of backticks in the text, so no line of the page ends the frame.
- **A fetched page may be cited.**: Its URL joins `allowed_urls`, because the model read it.
- **Count each call in `devops_cli_roadmap_page_fetches_total`.**: The counter of the client counts only the fetches that reach the service. This counter also counts the refusals and the limit, by job.

## Rejected alternatives

- **Let the model fetch any URL.**: A page chosen by the model, or by text in an earlier page, is a way to reach any host and to leak data in a URL. The guard keeps the URLs to those that a search or the item named.
- **Fetch inside `search_web` for each hit.**: It costs a fetch for each hit and fills the window of the model. The model chooses what to read.
- **A new agent framework for research.**: #3877 decides the research agent. This change adds one tool to two existing tool classes.
