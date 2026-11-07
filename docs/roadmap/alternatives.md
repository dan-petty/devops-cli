# The alternatives check

`devops roadmap alternatives` checks open items for an open, maintained tool or library that already covers their need, in whole or in part. It runs beside step 2 of [the roadmap workflow](../ROADMAP_WORKFLOW.md). The command help gives a summary only. This page gives the rest. The rules that a test checks are in the spec named at the end of this page.

## What a check does

For each item, one agent run searches the web through the providers of `search.providers` (SearXNG, DuckDuckGo and Firecrawl by default). A provider that is not configured is skipped. A provider that fails or returns no hit passes the search on to the next one, and the first provider with a hit answers. It reads the facts of each candidate tool from GitHub and PyPI: its license, its last activity and whether it is archived. When `crawl4ai.url` is set, the run also has the tool `fetch_page`, which reads the text of one page through the Crawl4AI service. It takes an https URL that a search of the same run returned or that the item text names, and no other URL; it sends no request for any other URL. A run fetches at most 3 pages. The tool frames the text as data from an outside page, never an instruction, and names the source URL and the fetch date so that a comment can cite them. A failed fetch is a tool answer and uses one fetch. Each call counts in `devops_cli_roadmap_page_fetches_total` by `toolset` (`refine` or `alternatives`) and `result` (`ok`, `refused`, `limit` or `error`). The tool is off with no `crawl4ai.url`.

The verdict is `covers`, `partly` or `none`. For every item except those named below, the check accepts a verdict only after the run searched. A reply with no search gets one more turn to search.

The model can propose two more verdicts: `rejected` and `in-use`. The job gives each one only when the text confirms it. If the text does not confirm a proposal, the job drops it and keeps the verdict of the reply. The model cannot give either verdict as its own. A reply with one gets one more turn. Refine asks a person nothing about a `rejected` or `in-use` check.

The comment of a `rejected` check names the ADR and keeps the tool URL, because a newer fact can change an ADR.

### What the check reads of the ADRs

Once for a run, when the run checks an item that is no skip class, the check reads the files `docs/adr/<four digits>-<name>.md` of the default branch. It keeps the number, the title, the status lines and the `Considered Options` section of each ADR. The status lines are the paragraphs under the title that name another ADR and say that it supersedes or amends. An ADR that a later ADR supersedes in whole is not in force, so the check leaves it out. An ADR that another ADR amends or supersedes in part stays, with its status lines.

The request holds the entries as `decisions`, the newest ADR first. The text has at most `CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS` tokens. The cut takes whole entries and never part of one. An entry that does not fit is left out, and a log warning names each ADR that the cut leaves out. The model cannot cite an ADR that it did not see, so the job confirms only the ADRs of `decisions`. A repository with no `docs/adr/` sends no `decisions`.

### How the job confirms a proposal

The model proposes `rejected` in the key `adr`, with the number of the ADR that rejected its tool. The job gives `rejected` when `decisions` holds that ADR and its title or options name the tool. The job does not read the sense of the ADR: the model reads it, and the comment shows the ADR number to a person.

The model proposes `in-use` in the key `in_use`. The job gives `in-use` when the title or the body of the item names the tool. It reads the body outside its own block and outside the refine section, because both name the tool of an earlier check. Without the flag of the model, the job never gives `in-use`.

The reply holds `tool_name` too: the name that the ADR or the item writes for the tool, such as `DBOS Transact`. The job tests the repository name or the package name, and `tool_name`.

A text names a tool by the rules below. The test ignores case, and takes a space, `-`, `_` and `.` as one separator. A letter, a digit, `_` or `-` next to a name means it is part of a longer word, so `pytest-cov` does not name `pytest`.

| Name | Where it counts |
| :--- | :--- |
| `owner/name` of the repository | Anywhere, a URL included |
| Two words or more, such as `argo-workflows` | Anywhere |
| One word, such as `just`, `task` or `requests` | In a code span, in the text or the target of a link, or in strong emphasis |

A name of one word is also a word of prose. So the word `just` in a sentence does not name the tool `casey/just`, and `` `just` `` does. The job reads the text with the markdown parser of the project to find these spans.

An item of the type `test`, `docs`, `refactor`, `chore`, `ci` or `perf`, and a `fix` with a stack trace, get `not-applicable` with no model call.

## What a check writes

With `--confirm`, a check does three things:

1. It posts one comment.
2. It replaces the block `devops-roadmap-alternatives` in the body of the item.
3. It records the check in the job record.

A check changes no label and closes no issue. A person decides what a tool means for the item.

The comment gives:

- the verdict and the reason of the model for it, in one or two sentences;
- the tool, with its URL, license and last activity, and what it covers and lacks;
- the tools considered: every tool whose facts the run read, each with its URL, license and last activity;
- the searches run, each with its number of results;
- at most five sources, and a line that says how many more the comment leaves out. GitHub shows each URL as a link.

A check adds a new comment. It never changes the comment of an earlier check.

## Which items a run takes

A run takes open New and Ready items that a trusted author opened. A trusted author is a person with write access, the Service App's bot or `github-actions[bot]`. A run takes an item of a bot only with the approval of the review of refine.

A run takes first the items with no check, lowest number first. Then it takes the items whose check is older than `roadmap.alternatives.recheck_days`, or whose text changed since. The setting `roadmap.alternatives.first_pass_limit` (20 by default) caps the run while an item has no check. The setting `roadmap.alternatives.limit` (5 by default) caps the run after, when every item has a check. `--limit` replaces both for one run. The row runs about twice a day, so a first pass of 141 items takes about 4 days.

`--item` checks one open item whoever opened it and whatever its Status, even when its check is current.

## When the check is off

The check is off for a private repository and when no search provider is configured. DuckDuckGo needs no key, so a public repository has a provider with the default settings. The plan says why.

## Failures

An item is skipped, reported and recorded in its job record when its model call fails, when its run stops, or when the job refuses its reply. The job writes the other items. The run takes a skipped item again after `roadmap.alternatives.retry_days`.

The command exits 1 only when it tried items and checked none.

## Modes

| Flag | What the run does |
| :--- | :--- |
| `--plan` (the default) | Runs the checks and prints them. It writes nothing. |
| `--confirm` | Writes each check to GitHub: its comment, its body block and its job record. |
| `--dry-run` | Makes no request. It prints the requests that a run makes, with placeholders. |

## Where the rules are

[roadmap-alternatives](../../openspec/specs/roadmap-alternatives/spec.md) holds the order of the items, the three tools of the agent, the checks on a reply, the comment and the block, the recheck and retry settings, and the skip class.
