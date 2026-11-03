# The alternatives check

`devops roadmap alternatives` checks open items for an open, maintained tool or library that already covers their need, in whole or in part. It runs beside step 2 of [the roadmap workflow](../ROADMAP_WORKFLOW.md). The command help gives a summary only. This page gives the rest. The rules that a test checks are in the spec named at the end of this page.

## What a check does

For each item, one agent run searches the web with Firecrawl. It reads the facts of each candidate tool from GitHub and PyPI: its license, its last activity and whether it is archived.

The verdict is `covers`, `partly` or `none`. For every item except those named below, the check accepts a verdict only after the run searched. A reply with no search gets one more turn to search.

An item of the type `test`, `docs`, `refactor`, `chore`, `ci` or `perf`, and a `fix` with a stack trace, get `not-applicable` with no model call.

## What a check writes

With `--confirm`, a check does three things:

1. It posts one comment.
2. It replaces the block `devops-roadmap-alternatives` in the body of the item.
3. It records the check in the job record.

A check changes no label and closes no issue. A person decides what a tool means for the item.

## Which items a run takes

A run takes open New and Ready items that a person with write access opened. It takes first the items with no check, lowest number first. Then it takes the items whose check is older than `roadmap.alternatives.recheck_days`, or whose text changed since. The setting `roadmap.alternatives.first_pass_limit` (20 by default) caps the run while an item has no check. The setting `roadmap.alternatives.limit` (5 by default) caps the run after, when every item has a check. `--limit` replaces both for one run. The row runs about twice a day, so a first pass of 141 items takes about 4 days.

`--item` checks one open item whoever opened it and whatever its Status, even when its check is current.

## When the check is off

The check is off for a private repository and when there is no Firecrawl key. The plan says why.

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
