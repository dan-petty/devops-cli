# Design

## Measured cause

The log line of #6346 is `The alternatives check of #<n> refused its reply (url): the reply cites <url>, and no tool of the run returned it.` Each refused URL below comes from one such line. Only devtools #29 is different: its run error line of 0.185.0 names its URL. The Crawl4AI log names the page that each run fetched. For each URL of the first case, the README of that page on GitHub holds the URL as a link, in the same form.

| Item | Refused URL | Page that the run fetched | Case |
| --- | --- | --- | --- |
| #4821 | `https://argo-workflows.readthedocs.io/en/latest/` | `https://github.com/argoproj/argo-workflows` | link in the fetched page |
| #4855 | `https://cli.github.com/manual/` | `https://github.com/cli/cli` | link in the fetched page |
| #6599 | `https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/` | `https://github.com/grafana/grafana-infinity-datasource` | link in the fetched page |
| #3027 | `https://docs.openhands.dev/openhands/usage/agent-canvas/prebuilt-automations` | `https://github.com/OpenHands/OpenHands` | link in the fetched page |
| #3027 | `https://docs.openhands.dev/openhands/usage/agent-canvas/backends` | `https://github.com/OpenHands/OpenHands` | link in the fetched page |
| #3770 | `https://openspec.dev/docs/setup` | `https://github.com/Fission-AI/OpenSpec` | link in the fetched page |
| #3770 | `https://openspec.dev/docs/supported-tools` | `https://github.com/Fission-AI/OpenSpec` | link in the fetched page |
| #4867 | `https://pydantic.dev/docs/ai/graph/graph/` | `https://github.com/pydantic/pydantic-ai` | link in the fetched page |
| #4867 | `https://pydantic.dev/docs/ai/evals/evals/` | `https://github.com/pydantic/pydantic-ai` | link in the fetched page |
| devtools #29 | `https://hub.docker.com/r/docker/buildx-bin` | devtools issue #19, which the item names | link in the fetched page |
| #4822 | `https://github.com/dan-petty/devops-cli/issues/4780` | none | URL that the item body names |
| #4842 | `https://github.com/dan-petty/devops-cli/issues/4833` | none | URL that the item body names |
| #2003 | `https://github.com/dan-petty/devops-cli/issues/1387` | `https://github.com/argoproj/notifications-engine` | URL that the item body names |
| #4866 | `https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Loops_and_iteration` | none | URL that no input holds |

- A link in the text of a fetched page, cited with no fetch of its own: 10 URLs in 7 runs.
- A URL on the `Source:` line of the item body, cited with no fetch: 3 URLs in 3 runs.
- A URL that is in no request, tool answer or comment of the run: 1 URL. The run made 3 searches about review findings and no fetch, so the model knew the URL from its training.
- A URL that a tool returned in another form (a redirect, the scheme, a fragment, a query, a slash, `www` or the case): 0 URLs. Each refused URL of a fetched page is the same text as the link in the page, and each fetch asked for another URL. The client follows no redirect, and `PageFetch` records the URL that it asked for.

The earlier result of an item is not the cause. 9 of the 11 items had an earlier check. But the earlier comments hold only 1 of the 14 URLs (`https://openspec.dev/docs/setup` of #3770), and the README that the run fetched also links it.

The prompt of 0.187.0 said "Do not write a URL that no tool gave you" and "Each one is a URL that a tool gave you". The answer of `fetch_page` holds the whole text of the page, with its links. Thus a link in the page is a URL that a tool gave the model. The check reads the rule otherwise: only the `Source` URL of the page joins `allowed_urls`.

## Decisions

- The answer of `fetch_page` says "A link in the text is not a source." next to the line that says to cite the source URL. The model reads it at the point where it reads the link. The sentence is true for refine too: refine drops each source that `allowed_urls` does not hold.
- The prompt of the alternatives check names the three kinds of URL that are sources. It also names the URLs that are not sources: a link in a page or a search result, a URL from memory, and a URL that the issue or a comment names, until `fetch_page` reads it. This covers the 3 URLs of the item body and the URL from training.
- The check stays as it is. A reply that cites a link of a page, or a URL that the item names and that no tool read, stays refused for reason `url`.

## Rejected alternatives

- Add each link of a fetched page to `allowed_urls`. It loosens the check: the job then accepts a source that no tool read. A page that an outside person writes can then put any URL in a comment of the job.
- Let `fetch_page` fetch each link of a fetched page. It widens the boundary of the tool (`roadmap-page-fetch`, "A fetch needs a named https URL"). A page that an outside person writes then chooses the URLs that the job requests.
- Remove the link targets from the page text. The `POST /md` endpoint of Crawl4AI has no option for it. Code in this project that removes Markdown links is a parser of our own, and it misses bare URLs and reference links.
- Turn on `alternatives.reply_fixable` in the live config. It sends a refused reply back to the model once, so each refusal costs one more model call. The model still cites the link first. It is a decision of a person, and this change does not need it.
- Normalize more forms of a URL in `normalize_url`. No refused URL differs from a tool URL in its form, so it changes no measured refusal.
