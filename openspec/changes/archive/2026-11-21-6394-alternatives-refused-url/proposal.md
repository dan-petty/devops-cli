# Proposal: #6394

## Why

The alternatives job is below its target of 80% success. On 2026-11-21 it had 30 successes in 40 results in 6 hours, and 91 in 120 in 24 hours. On 0.186.0 and 0.187.0, each failed result is `refused` with `reason=url`, after 3 to 10 answered searches. The WARNING lines of #6346 name the refused URLs. Closes #6394.

In 10 of the 14 refused URLs, the model cites a link from the text of a page that `fetch_page` read. No tool returned that link. The prompt of 0.187.0 told the model to cite "a URL that a tool gave you". The answer of `fetch_page` holds each link of the page. Thus the model reads a link in the page text as a URL that a tool gave it.

## What Changes

- The answer of `fetch_page` says that a link in the text is not a source. The investigation of refine and the alternatives check get the same answer.
- The prompt of the alternatives check names the URLs that are sources. These are the URL of a `search_web` result, the `Source` URL of a page that `fetch_page` read, and the first URL of the answer of a fact tool.
- The prompt says that a URL is a source only when a tool gave it in one of these ways. A URL that the issue, a comment, the text of a page, a search snippet or the memory of the model holds is a source only in that case.
- The check does not change: a source that no tool returned stays refused.
- The answer of a tool is observable, so the change carries a delta of `roadmap-page-fetch` and of `roadmap-alternatives`.

## Capabilities

- `roadmap-page-fetch`: MODIFIED requirement 'The page text reaches the model as data'.
- `roadmap-alternatives`: ADDED requirement 'A link in a fetched page is not a source'.

## Impact

Each page answer tells the model of the alternatives check and of refine not to cite a link of the page. No new step, gate, cap, retry or setting. The decision point `alternatives.reply_fixable` does not change.

## Feasibility

- Loki, `{namespace="devops", container="service"} |~ "cites"`, read on 2026-11-21 at 07:10 UTC: 13 WARNING lines of 0.186.0 and 0.187.0. One more line is the run error of devtools #29 on 0.185.0. Together they give 14 refused URLs in 11 runs. The design gives each URL and its case.
- Loki, `{container="crawl4ai"}`: each page that a refused run fetched.
- Tempo, the trace of the round that started on 2026-11-21 at 06:32 UTC: the tool calls of each refused run of that round.
- `src/devops_cli/roadmap/alternatives.py` at ba37ab4f3: `_unknown_urls` compares `normalize_url(url)` with `AlternativesTools.allowed_urls`. That set holds each search result URL, each fetched page URL and each fact URL.
- `tests/roadmap/test_roadmap_alternatives_page_links.py` replays the measured run offline.

## Existing Tool Considered

No open tool covers the need. The cause is the text that this job gives its model, and only the prompt and the tool answer of the job can change it. The change edits two texts and adds one test file. It costs about 40k tokens and 2 hours to build and keep. It deletes no internal code.

This change fits one pull request.
