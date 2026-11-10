# Design

## Decisions

- **The record is a table in `audit.md`.** One row for each place, so a reader finds the decision and its reason in one line. Each row names the file and line, so a later `git grep` can check the row.
- **Compare Crawl4AI first, Firecrawl second.** Crawl4AI is open source, runs in the cluster, costs no credits and keeps data in the network. Firecrawl stays a candidate only for what Crawl4AI lacks: a call from a workstation or a Job pod, and a link crawl.
- **A place that reads private data never adopts a hosted tool.** No place of the census reads private data through a web fetch, but the rule decides the rows of `ingest_remote_docs` (a person gives the URL) and of the knowledge-base sources.
- **Adopt only on evidence of a failure.** A place changes tool when its current code fails on a page that the other tool serves. The census holds no such evidence, so every row is `keep`.
- **The audit changes no code.** The diff holds no file under `src/`, and a task checks that with a command.

## Rejected alternatives

- **Compare Firecrawl only.** It ignores the Crawl4AI service that the project already runs. The service answers `POST /md` at no credit cost (`k8s/README.md`, section Crawl4AI).
- **Adopt Firecrawl `/v2/crawl` for `ingest_remote_docs` now.** It costs 1 credit for each page, up to 10 pages for each run at the default `--max-pages`, and adds a hosted dependency and a key to a command that a person runs on a workstation. The census holds no page that the own parser fails on. The reason to reject is the missing evidence, not the cost of the change.
- **Adopt Crawl4AI `/md` for `ingest_remote_docs`.** The perimeter lets only the pods of `roadmap-service` call the service, so a workstation command cannot reach it. `/md` also returns no link list, so the page walk would need the own code anyway.
- **File an item for a knowledge-base drift check.** No feature reads the `sources:` URLs today, so the audit has no place to decide. A new feature is a new issue, not an audit result.
