# The alternatives check

`devops roadmap alternatives` checks open items for an open, maintained tool or library that already covers their need, in whole or in part. It runs beside step 2 of [the roadmap workflow](../ROADMAP_WORKFLOW.md). The command help gives a summary only. This page gives the rest. The rules that a test checks are in the spec named at the end of this page.

## What a check does

For each item, one agent run searches the web through the providers of `search.providers` (SearXNG, DuckDuckGo and Firecrawl by default). A provider that is not configured is skipped. A provider that fails or returns no hit passes the search on to the next one, and the first provider with a hit answers. It reads the facts of each candidate tool from GitHub and PyPI: its license, its last activity and whether it is archived. The PyPI facts come from the fact cache of the project brain for 24 hours, in the memory of the process and in the cache Valkey `valkey-devops`, so a package that a process or another pod read sends no request, and a failed read keeps nothing (#4668). When `crawl4ai.url` is set, the run also has the tool `fetch_page`, which reads the text of one page through the Crawl4AI service. It takes an https URL that a search of the same run returned or that the item text names, and no other URL; it sends no request for any other URL. A run fetches at most 3 pages. The tool frames the text as data from an outside page, never an instruction, and names the source URL and the fetch date so that a comment can cite them. It also says that a link in the text is not a source (#6394). A failed fetch is a tool answer and uses one fetch. Each call counts in `devops_cli_roadmap_page_fetches_total` by `toolset` (`refine`, `alternatives` or `stage`) and `result` (`ok`, `refused`, `limit` or `error`). The tool is off with no `crawl4ai.url`. When `crawl4ai.url` is set, the run also has the two ask-mode research tools `research_lookup` and `research_grep`. Under the store-first rule, `research_lookup` checks the SQLite research index first. When an answer is missing or older than `roadmap.research.answer_expiry_days` (default 30 days), it searches the web and fetches the top page to update the index. `research_grep` searches stored page texts by exact term or regular expression pattern. The query guard refuses empty queries, secrets, e-mail addresses, private addresses and internal hostnames before sending any network request. A run makes at most `roadmap.research.max_calls_per_run` (default 20) research tool calls.

The verdict is `covers`, `partly` or `none`. For every item except those named below, the check accepts a verdict only after the run made an answered search. A search that no provider answered, and a refused query, do not count. A reply with no answered search gets one more turn to search. Every call of `search_web` counts toward the limit of searches.

The prompt names the URLs that a source can cite. These are the URL of a search result, the source URL of a page that `fetch_page` read, and the URL on the first line of a fact read. The job refuses a reply that cites any other URL (#6394). A link in the text of a page, or a URL that the item names, is a source only when a tool also gave it in one of these ways.

The model can propose two more verdicts: `rejected` and `in-use`. The job gives each one only when the text confirms it. If the text does not confirm a proposal, the job drops it and keeps the verdict of the reply. The model cannot give either verdict as its own. A reply with one gets one more turn. Refine asks a person nothing about a `rejected` or `in-use` check.

The block of a `rejected` check names the ADR and keeps the tool URL, because a newer fact can change an ADR.

### What the check reads of the ADRs

Once for each run, before it selects the items, the check reads the files `docs/adr/<four digits>-<name>.md` of the default branch. It keeps the number, the title, the front matter and the `Considered Options` section of each ADR. The front matter holds the status of the ADR and its links to other ADRs ([docs/adr/README.md](../adr/README.md)). Only an ADR in force reaches the request: an ADR with `status: accepted`, or with no status, that no ADR supersedes. An ADR that another ADR amends stays, and its entry names the ADRs that amend it. A front matter that is not valid stops the run with an error that names the file.

The request holds the entries as `decisions`, the newest ADR first. The text has at most `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS` tokens. The cut takes whole entries and never part of one. An entry that does not fit is left out, and a log warning names each ADR that the cut leaves out. The model cannot cite an ADR that it did not see, so the job confirms only the ADRs of `decisions`. A repository with no `docs/adr/` sends no `decisions`.

### How the job confirms a proposal

The model proposes `rejected` in the key `adr`, with the number of the ADR that rejected its tool. Unless the tool is the item's own repository (which always gets `in-use`), the job gives `rejected` before testing the inventory when `decisions` holds that ADR, an item of its `Considered Options` list names the tool as the option's subject (head noun, versioned head, multi-word product compound, or explicit `owner/name` outside link targets), ignoring link targets, modifiers such as `Kubernetes Lease` or `` `gh` CLI ``, prepositional instruments after `through`, and packaging methods such as `bundling`. No chosen or adopted option may name the tool. A chosen or adopted option that names the tool wins even when it also says `not chosen` or `not adopted`. ADR 0010 names OpenSpec in its chosen option and in other options, so it rejects no OpenSpec. The block shows the ADR number to a person.

The model proposes `in-use` in the key `in_use`. The job gives `in-use` when the title or the body of the item names the tool. It reads the body outside its own block and outside the refine section, because both name the tool of an earlier check. Without the flag of the model, the text of the item never gives `in-use`. The tools in use can (see [The tools in use](#the-tools-in-use)).

The reply holds `tool_name` too: the name that the ADR or the item writes for the tool, such as `DBOS Transact`. The job tests the repository name or the package name, and `tool_name`.

A text names a tool by the rules below. The test ignores case, and takes a space, `-`, `_` and `.` as one separator. A letter, a digit, `_` or `-` next to a name means it is part of a longer word, so `pytest-cov` does not name `pytest`.

| Name | Where it counts |
| :--- | :--- |
| `owner/name` of the repository | Anywhere, a URL included |
| Two words or more, such as `argo-workflows` | Anywhere |
| One word, such as `just`, `task` or `requests` | In a code span, in the text or the target of a link, or in strong emphasis |

A name of one word is also a word of prose. So the word `just` in a sentence does not name the tool `casey/just`, and `` `just` `` does. The job reads the text with the markdown parser of the project to find these spans.

An item of the type `test`, `docs`, `refactor`, `chore`, `ci` or `perf`, and a `fix` with a stack trace, get `not-applicable` with no model call.

### The tools in use

Once for a run that checks an item of no skip class, the check reads the inventory of the repository at HEAD. A `covers` or `partly` tool that the inventory holds gets `in-use` with no proposal of the model. An ADR that rejects the tool comes first. The block says "The repository already uses this tool." The inventory has three sources, the cheapest first:

1. The SPDX SBOM that the dependency graph of the repository exports (`GET /repos/{owner}/{repo}/dependency-graph/sbom`), with one request. It holds the package URL of each package of a manifest, a lock file or a workflow. A PyPI package matches by its canonical name, an action by its repository (`pkg:githubactions/github/codeql-action/init` is `github/codeql-action`), and the npm package `@<owner>/<name>` by the repository of the same name. A dependency graph that is off gives an empty SBOM.
2. The files under `roadmap.alternatives.inventory_paths` of a clone (`k8s`, `tf`, `.devcontainer`, `src/devops_cli/config/commands.py`, `src/devops_cli/roadmap/runner_tools.py` and `src/devops_cli/infra/ansible_facts.py` by default). They name the services, images and CLIs that no manifest holds, such as LiteLLM, Grafana or kubectl. The three source files name, with no version, the commands that devops-cli starts, each program that a Job needs or leaves out, and the Ansible commands; they take the place of the tools lock (#4363). The name of the repository or of the package counts as a whole word in any case, as `git grep -i -w -F` finds it. The Service row uses the clone of its lane. On a workstation, `--source <clone>` gives the clone, and with no clone the check uses the other two sources.
3. deps.dev, which links a GitHub project to the packages whose source it is (`GET https://api.deps.dev/v3/projects/<project>:packageversions`). The repository `modelcontextprotocol/python-sdk` is the PyPI package `mcp` of the SBOM. The check asks deps.dev only when the SBOM holds a package and the earlier checks do not match, and one run asks once for each project. The answer comes from the same fact cache for 24 hours. A failed read skips the item, and the run takes it again after `roadmap.alternatives.retry_days`.

Before asking deps.dev, the check matches a language's standard library repository (`python/cpython`, `golang/go`, `rust-lang/rust`, `ruby/ruby`, `dotnet/runtime`, or `nodejs/node`) if the SBOM holds a package of that type or if a deployed file uses a suffix of that language (#6347).

The inventory lives for one run.

### The canonical id and the ADR hash

A check records the canonical id of its tool in `alternatives.tool_id`, so the verdicts of one tool join whatever its URL. The id is the deps.dev project key of the GitHub project of the tool, `github.com/<owner>/<name>` in lower case. A PyPI tool takes its project from the `Source`, `Repository` or `Code` URL of its PyPI record, then from its home page. A PyPI tool with no GitHub source has the id `pkg:pypi/<name>`, with the canonical name of `packaging`. Another URL is its own id.

A check of an item of no skip class also records `alternatives.adr_hash`, the hash of the ADR entries that the model saw. When the ADRs at HEAD give another hash, the item is due again (see [Which items a run takes](#which-items-a-run-takes)).

## The reference step

After the verdict of an item, the reference step looks for reference implementations in public code and for official documentation (#4672). It runs for each checked item, also for an item of a skip class. The setting `roadmap.alternatives.references` is its mode:

| Mode | What the step does |
| :--- | :--- |
| `off` | It runs nothing. |
| `plan` (the default) | It searches and verifies. It writes each verified link to the log and counts it. It changes no issue text and no job record. |
| `on` | It also gives the links to the check, which writes them in the block, in the comment and in `alternatives.refs`: at most 3 permalinks and at most 3 documentation links. |

The check writes the links of the step only in mode `on`, and only when the step ran to its end or found a link. A step that failed, or that passed its bound, says nothing about the item. Then, and in mode `plan` and mode `off`, the check shows the links that `alternatives.refs` holds from an earlier check, and its write leaves the block and the record as they are. So a rate limit removes no link, and a switch from `on` back to `plan` changes no issue text.

The step makes no model call of its own. Its queries come from two sources:

- The rule queries of the item body: each Python import statement, then the name of each package that a URL of the body names (a PyPI project or a GitHub repository), then each other code span.
- At most 3 `reference_queries` of the model reply of the same check. An item of a skip class has no reply, so it sends the rule queries only.

The step takes a rule query and a query of the model in turn, and it sends at most 3 queries for an item. A query is plain words: a colon and a quote leave it, so no text of an item names a search qualifier.

Each query passes the query guard of the web search before it reaches a provider or the decision point. The guard refuses a secret, an e-mail address, a private address and an internal host name. It reads the text of the item and also the plain words, because the host of a URL is a word of its own only there. A refused query is dropped and counted with the provider `step` and the result `refused`. A text of the item that the URL parser refuses, such as `https://[name]:6443/healthz`, names no URL and stops no step.

The providers are data:

- `github-code` is GitHub's code search (`GET /search/code`, at most 10 requests a minute). It answers a query with files.
- `github-repository` is GitHub's repository search (`GET /search/repositories`, at most 30 requests a minute). The step sends it one query for an item, which names the repositories of all code hits, and takes the facts of each repository from the answer.
- `mcp-code` is an optional provider: the code search tool of the MCP server that `roadmap.alternatives.references_mcp_url` names, such as the grep.app server (`https://mcp.grep.app`). The step uses the first tool of the server that has a `query` argument, and it reads each link to a file on GitHub in the answer as a code hit. With this provider, each second query goes to it. Its connection uses an HTTP client of `devops_cli.http.entry` at the public egress level. The connection and the tool listing have the bound of one tool call (`roadmap.mcp.timeout_seconds`). Each error of the MCP client at the connection, the tool listing, a call, the answer or the close is one error of the provider: the server is unavailable. A provider that fails at a call ends its connection and gets no later query of the run. The failed query goes to `github-code` when the item has a code search left.

Both GitHub searches go through the paced GitHub session, and one search is one request of one page. The run connects an optional provider at its start. A server that is down then is left out, and the check continues with the other providers. A private repository gets the two GitHub providers only, so no text of its items goes to another host. The setting has no URL by default, so the step has the two GitHub providers until a person sets one. The queries of a public item then go to that server.

The gates and the rank are code:

- A hit passes the gates only when it is a code hit, and its repository is public, not archived, not a fork, pushed in the last 365 days, under a license that the OSI approved, not this repository and not linked already in the item. A code hit names a file that is no prose: a file with the suffix of a Markdown, text, reStructuredText, AsciiDoc or HTML file is no implementation. A path with an empty segment, `.` or `..` is no path of a file.
- The rank of a candidate is the sum of the base-10 logarithm of its stars, the base-10 logarithm of the direct dependents that deps.dev counts for its PyPI package (`GET https://api.deps.dev/v3alpha/systems/pypi/packages/<name>/versions/<version>:dependents`), the number of PyPI packages of the SBOM whose source it is, and 1 when its head holds a directory `tests` or `test`. The deps.dev facts come from the fact cache of the project brain.

The step verifies each link before it keeps it. For a candidate, it reads the head commit of the default branch and then the file with `repository_file` at that commit. A path that the head commit does not hold gives no link. `render_permalink` gives the link `https://github.com/<owner>/<repo>/blob/<sha>/<path>#L<a>-L<b>`. The link starts at the first line that holds the longest word of the query, or at line 1, and it covers at most 20 lines. A line ends at a line feed only, as GitHub counts the lines of a file. The step keeps at most 3 permalinks. A path and a documentation URL are text of another repository or host. The link holds the path percent-encoded, and a documentation URL with a character that is no URL character gives no link, so no link writes markup into an issue.

A documentation link is a source of the check, or a documentation hit of a provider. The step keeps it only when its URL is `https`, its host is on the allowlist `CONST_ROADMAP_ALTERNATIVES_REFERENCE_DOC_DOMAINS`, the item does not link it already, and one request of the page answers 200. The request is for the URL as the search gave it, with its last slash, and it follows no redirect: a redirect is no answer. The step reads at most 3 pages for an item, so the code candidates keep their fact reads. The allowlist is a constant: `ai.pydantic.dev`, `docs.astral.sh`, `docs.github.com`, `docs.pydantic.dev`, `docs.python.org`, `kubernetes.io`, `opentelemetry.io` and `typer.tiangolo.com`. Only a reviewed code change adds a host. The step keeps at most 3 documentation links, beside the at most 3 permalinks.

The step has bounds for one item: at most 3 code searches, at most 15 fact reads, and 120 s. A fact read is each request that is no code search. The step fails soft. A failed search, a failed read, a spent GitHub quota and a passed time bound each give a warning in the log and fewer links, and the check writes its verdict as before. The step runs in a thread of its own. After the bound it sends no new request, and a request in flight ends at its own timeout. An error of the step that is no project error ends that thread, which reports it with its trace, and the round goes on.

The counter `devops_cli_brain_references_total` counts each search by `provider` and `result` (`hit`, `empty` or `failed`). A verified link adds 1 with `verified` in mode `plan`, or with `linked` when mode `on` writes it. Under the provider `step`, a refused query adds 1 with `refused`, a passed time bound adds 1 with `timeout`, and a step that ended with an error adds 1 with `failed`. The result line of the job gives the number of verified links in `references`.

The decision point `brain.reference_relevance` (ADR 0023, section 7) asks the decision model one question about each permalink that the step keeps: is the candidate file off the need of the item? The point runs in `shadow` only. Its record and its count go to the log and to `devops_cli_decision_point_total`, and no band changes a link. Its cuts file holds start cuts with no labelled case, so the settings refuse the mode `on` until a fit. The point asks nothing for a private repository.

## What a check writes

With `--confirm`, a check does these things:

1. It replaces the block `devops-roadmap-alternatives` in the body of the item and records the check in the job record. One request writes both, so a stop never leaves the new block without the record of the check.
2. It posts one comment, in a separate request after the write, for a first check and for a recheck whose verdict or tool differs from the record of the earlier check. A recheck with the same verdict and the same tool posts no comment: the thread shows only changes. Its block holds the new date, and its record holds the new check time. A check of a skip class posts no comment, because it has no evidence.

A check changes no label and closes no issue. A person decides what a tool means for the item.

The block holds the current result of the check:

- the date and the verdict;
- the skip class, for an item of a skip class;
- the basis of a `rejected` or `in-use` verdict;
- the tool on one line, with its URL, license, last activity and maintained state;
- the reason of the model for the verdict;
- what the tool covers and lacks;
- in mode `on` of the reference step, the permalinks under `Reference implementations:` and the documentation links under `Official documentation:`.

The comment is the event of a change of the result. It repeats no line of the block. It gives:

- one line. It says that the result in the block of the issue body changed, and what the result was before the check. It also says that a person decides what the new result means for the item;
- in mode `on` of the reference step, the links of the step, as the block lists them;
- one block that GitHub shows closed, `Searches (<count>)`. It holds the tools considered: every tool whose facts the run read, each with its URL, license and last activity. It also holds the answered searches with their number of results. Last, it holds every source of the reply. GitHub shows each URL as a link.

The prompt asks the model for a brief reply: a reason of one sentence, and a few short items in `covers`, `lacks` and `sources`. The check refuses no reply for its length and cuts no text or list of the model.

Refine reads the result from the block, and the evidence from the latest comment of the job, whole. A comment of an older form also holds what the tool covers and lacks. Refine reads them there when the block has no such list.

A check that posts a comment adds a new one. It never changes the comment of an earlier check.

In mode `on` of the reference step, the job record holds the links of the check in `alternatives.refs`, with a space between them. A check whose step ran to its end and found no link clears the key. A change of the links alone is no change of the result, so it posts no comment: the head commit of a repository moves, and the links move with it.

## The brain index

After its checks, the alternatives row of the Service runs `brain-sync` (#4676, [ADR 0023](../adr/0023-the-project-brain-is-a-derived-index-in-two-cache-tiers-and-two-scheduled-runs-keep-it.md), section 3). The step copies the result of each check into the brain index of `valkey-roadmap` ([docs/CLUSTER.md](../CLUSTER.md#valkey-roadmap)), so a reader finds the verdicts, the tools and the references of a repository in one place. `devops roadmap alternatives` on a workstation writes no index: the next round of the row copies its checks.

- **The source.** The step reads the issues that the round already holds: the listing snapshot and the writes of the round. It sends no GitHub request and makes no model call. The block and the keys `alternatives.*` of the job record are the durable copy, so a lost index is built again from them.
- **The keys.** `RepoRef` builds each key, and each name holds the schema version `v1`.

  | Key | Holds | Ends |
  | :--- | :--- | :--- |
  | `roadmap:v1:brain-item:<owner>/<name>:<n>` | A hash: `verdict`, `tool_id`, `refs` (at most 3 reference ids), `near` (at most 5 items), `checked_at`, `body_hash`, `adr_hash`, `state`, `uses` (at most 10 entries of `alternatives.brain_used`) and `schema` | 45 days after its last write |
  | `roadmap:v1:brain-tool:<owner>/<name>:<id>` | A hash: the canonical id of the tool, its URL, the name that the check wrote, and the items that name it. `<id>` is 16 hex characters of the hash of the canonical id | 45 days after its last write |
  | `roadmap:v1:brain-ref:<owner>/<name>:<id>` | A hash: the URL of a reference repository and the items that link it. `<id>` is 16 hex characters of the hash of the URL | 45 days after its last write |
  | `roadmap:v1:brain-events:<owner>/<name>` | A stream with one entry for each write of an item, about 10,000 entries. It is an audit trail, and no job reads it as a trigger | 45 days after its last write |
  | `roadmap:v1:brain-sync:<owner>/<name>` | A hash: the watermark of the step | No TTL. The step is its one owner |

- **Trusted authors only.** The repository is public, and the body of an issue holds its job record. So an account with no write access can write a block and a record of its own. The check takes only the items of trusted authors ([Which items a run takes](#which-items-a-run-takes)), and the step takes only their issues: the issue of another author gets no entry, and no tool or reference entry names it. Thus the check of an outside author's issue that a person ran with `--item` is not in the index.
- **A record of a wrong form.** A person can change a record by hand. No value of a record stops the step: a verdict or a time of a wrong form gives no entry, a time with no zone is a time in UTC, a tool URL that is no URL is its own id, and a link that is no URL is no reference.
- **References and near items.** A reference is the GitHub repository of a link of `alternatives.refs`, one time for each repository. The near items of an item are the other items of the same repository whose check names the same tool, the newest check first. An entry never names an item of another repository.
- **One item, one transaction.** The hashes of one item and its stream entry go in one MULTI/EXEC, so an entry is whole, old or new.
- **The newer check wins.** The transaction reads the `checked_at` of the entry that the index holds. When that time is newer than the one of the block, the entry stays. In each other case the block replaces it, because GitHub holds the durable copy.
- **The watermark.** The step keeps the `updated_at` and the number of the last issue that it examined. It copies each issue that changed after that place, at most 500 in one round, and the next round goes on from there. So the first round copies each check, and a round after an outage copies each issue that changed in it.
- **A store that is down.** With no `roadmap.state.url`, or while the store does not answer, the round ends as before and adds one `fallback` to `devops_cli_brain_reads_total{store="brain_index"}`. A reader of the index has a miss.
- **A private repository.** The check is off for a private repository, so it has no block, and the step makes no sync for it.
- **Instruments.** `devops_cli_brain_entries` gives the item entries of a repository. `devops_cli_brain_sync_lag_seconds{store="brain_index"}` gives the time since the end of the last sync: the row runs about six times a day, so its bound is the interval of the row and the time of one round. `devops_cli_brain_first_reads_total` counts the checks whose item the index held no entry for. `devops_cli_brain_writes_total{store="brain_index"}` counts each write as `shared`, as `older` when the index holds a newer check, or as `skipped` when the store did not answer.

## Which items a run takes

A run takes open New and Ready items that a trusted author opened. A trusted author is a person with write access, the Service App's bot or `github-actions[bot]`. A run takes an item of a bot only with the approval of the review of refine.

A run takes first the items with no check, lowest number first. Then it takes the items whose check is older than `roadmap.alternatives.recheck_days`, or whose text changed since, or, for an item of no skip class, whose `alternatives.adr_hash` differs from the hash of the ADRs at HEAD or is not recorded. The setting `roadmap.alternatives.first_pass_limit` (20 by default) caps the run while an item has no check. The setting `roadmap.alternatives.limit` (5 by default) caps the run after, when every item has a check. `--limit` replaces both for one run. The row runs about six times a day, so a first pass of 141 items takes about a day and a half.

`--item` checks one open item whoever opened it and whatever its Status, even when its check is current.

## When the check is off

The check is off for a private repository and when no search provider is configured. DuckDuckGo needs no key, so a public repository has a provider with the default settings. The plan says why.

## Failures

An item is skipped, reported and recorded in its job record when its model call fails, when its run stops, when its read of deps.dev fails, or when the job refuses its reply. The job writes the other items. The run takes a skipped item again after `roadmap.alternatives.retry_days`.

The result line of a skipped item gives in `searches` the searches that a provider answered before the failure, and in `returns` the replies that the run sent back to the model. When the job refuses a reply because a source cites a URL that no tool of the run returned (reason `url`), it logs one warning for each such URL, with the item number and the URL (#6346).

The job writes the check of an item before it checks the next item. A kill of the worker loses at most the check in progress. A rate limit on a write ends the round, and the checks that are written stay.

The command exits 1 only when it tried items and checked none.

## Modes

| Flag | What the run does |
| :--- | :--- |
| `--plan` (the default) | Runs the checks and prints them. It writes nothing. |
| `--confirm` | Writes each check to GitHub as soon as the item is checked: its body block, its job record and, for a first or changed result of an item that is no skip class, its comment. |
| `--dry-run` | Makes no request. It prints the requests that a run makes, with placeholders. |

## Where the rules are

[roadmap-alternatives](../../openspec/specs/roadmap-alternatives/spec.md) holds the order of the items, the three tools of the agent, the checks on a reply, the comment and the block, the recheck and retry settings, the skip class, the tools in use, the canonical id, the ADR hash and the reference step. [project-brain/index](../../openspec/specs/project-brain/index/spec.md) holds the brain index: its keys, the sync, the watermark, the transaction of an item and the instruments.
