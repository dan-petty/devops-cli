# Proposal

## Why

The roadmap jobs search the web with one thin chain and keep no answer, so refine, the alternatives check and the stage planner ask the same research questions every round. Item #3877 asks for an ADR that compares open research agents and tools, chooses one design or none, and fixes the research index, the string-match tool, the limits and the measure that the follow-up work builds.

## What Changes

- Add `docs/adr/0028-a-research-agent-composes-open-tools-and-a-research-index.md`, the accepted record: at least four open tools with the gap of each, the chosen composition, the rejected options with their evidence, the research index (source URL, fetch date, content hash, expiry, question, deduplication), the string-match tool, the limits and the follow-up work.
- Record the ten-question measure in the record: the question IDs, the hit rate and the cost per question, from the run that the approving person records on #3877.
- Regenerate the index table of `docs/adr/README.md` with `uv run devops docs generate`, so the new row and the record land in one step.
- The change has no spec delta: every path is under `docs/`, and a decision record adds no behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `docs/adr/0028-a-research-agent-composes-open-tools-and-a-research-index.md`, `docs/adr/README.md`

## Feasibility

- The fault was the citation of the docs command reference, whose code span the previous reply left open. This reply cites the index command only through the records README, and every citation closes its code span.
- Probe line, word for word: The path `SECURITY.md` is a file of the staging commit.
- Probe line, word for word: The path `src/devops_cli/config/defaults.py` is a file of the staging commit.
- Probe line, word for word: The path `docs/adr/0005-review-findings-come-from-tools-not-models.md` is a file of the staging commit.
- Probe line, word for word: The path `src/devops_cli/ai/web_search.py` is a file of the staging commit.
- Probe line, word for word: `ddgs` has no definition at the staging commit. No commit in the history added or removed its text.
- The premise that the jobs search the web through one thin chain holds: `src/devops_cli/ai/web_search.py:3:`in order and returns the hits of the first`, read with `read_file` of lines 1 to 12.
- The alternatives check searches through that chain: `docs/roadmap/alternatives.md:7:`searches the web through the providers of`, read with `read_file` of lines 1 to 15.
- The stage planner has the same tool: `docs/roadmap/stage.md:53:`It searches the web for alternative open tools and libraries`, read with `read_file` of lines 45 to 60.
- The provider order is the settings default: `docs/CONFIGURATION.md:350:`['searxng', 'duckduckgo', 'firecrawl']`, read with `read_file` of lines 340 to 360.
- The repository already holds a research package that reads the codebase and no web page: `src/devops_cli/commands/ai_research.py:16:`from devops_cli.ai.research.crawler import ForageCrawler`.
- A runner Job pod cannot reach SearXNG: `docs/CLUSTER.md:89:`A runner Job pod cannot reach SearXNG.`, found with `search_code` of `cannot reach SearXNG`.
- The Firecrawl key reaches the pod of the deployment that reads it: `k8s/README.md:769:`DEVOPS_CLI_FIRECRAWL_API_KEY`, read with `read_file` of lines 760 to 775.
- The command that writes the index exists and the records README names it: `docs/adr/README.md:142:`writes this table from the front matter of each record`, found with `search_code` of `writes this table from the front matter`.
- The record keeps the limits of the records folder: `docs/adr/README.md:75:`a body of 1,000 words or fewer`, and the staged constants are `src/devops_cli/docs/adr_records.py:31:_LAST_RECORD_BEFORE_RULES: Final = 25`, `src/devops_cli/docs/adr_records.py:32:_MAX_BODY_WORDS: Final = 1000`, `src/devops_cli/docs/adr_records.py:33:_MAX_TITLE_WORDS: Final = 10` and `src/devops_cli/docs/adr_records.py:34:_MAX_SLUG_CHARACTERS: Final = 60`.
- The staged code takes the slug after the first hyphen: `src/devops_cli/docs/adr_records.py:158:`slug = name.removesuffix(".md").partition("-")[2]`, so the new slug is 57 characters and within the bound of 60.
- An accepted record carries its body hash: `docs/adr/README.md:30:`An accepted record has it.`, and the test prints the hash of a body that has none: `docs/adr/README.md:39:`gives the hash of the body when the front matter has none`.
- The index row and the record land together, because the test compares the table with the records: `tests/invariants/test_adr_records.py:25:assert sync_index(page, read_record_texts(ADR_DIRECTORY)) == page` and `tests/invariants/test_adr_records.py:19:assert record_problems(read_record_texts(ADR_DIRECTORY)) == []`.
- The next record number is 0028: `list_files` of `docs/adr` lists `docs/adr/0027-dependency-updates-come-from-self-hosted-renovate.md` as the newest record.
- Functions that the plan calls, with their preconditions: `read_record_texts` needs a checkout of the repository, and `web_search` needs a network to each provider of the search chain.
- The measure cannot run in the implement step: a runner Job pod cannot reach SearXNG (`docs/CLUSTER.md:89`), and the Firecrawl key reaches the pod of the Service deployment and no runner pod (`k8s/README.md:769`). A person runs the ten questions on a workstation and records the hit rate and the cost per question on #3877.
- The staged `SECURITY.md` numbers egress as rule 2 and hosted models as rule 13, and the issue's parenthetical gives rule 13 for egress and private code. The record cites each rule by its number and its own text, and it plans no code that compensates for the mismatch.
- The verify program is in the runner image: `uv run devops ci test tests/invariants/test_adr_records.py` runs pytest, which the image holds and NOT_IN_RUNNER does not name, so a failure is class `test`. A generated-document difference that `uv run devops docs generate` leaves is class `lint`.
- The pod sets `readOnlyRootFilesystem: true`, so the step writes the record and the index only in the clone of its checkout.
- When the approving person records no run of the ten questions on #3877, the step stops with `premise_false` and the item returns to New with that evidence; the plan writes no number of its own.
- The step reads the approving person's comment from the item it already holds, so the plan adds no command, no client and no network path to the repository.

## Existing Tool Considered

SearXNG, Crawl4AI, ripgrep and Qdrant are the open, maintained tools that cover the need, and `ddgs` already serves the DuckDuckGo provider; the record composes them behind `pydantic-ai` and builds no agent of its own.

## Dependencies

None.
