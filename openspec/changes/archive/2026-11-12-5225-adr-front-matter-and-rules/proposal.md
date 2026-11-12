# Proposal: #5225

## Why

The architecture decision records of `docs/adr/` have no structure for their status, and no rule controls their life (#5225, child 1 of tracker #5233):

- Records 0001 to 0017 have no status section, and the other records hold their status in prose.
- 38 of the 49 commits that changed `docs/adr/` since 2026-10-25 edited an accepted record in place.
- The records in force give the alternatives check 8,464 tokens against its cap of 8,192 tokens, so the check leaves out ADR 0001 and ADR 0003. Status prose is 1,121 of those tokens.
- `src/devops_cli/roadmap/adr.py` reads the status from prose with three patterns: `_STATUS_VERB`, `_SUPERSEDED_BY` and `_SUPERSEDES`.
- `docs/adr/` has no index (#4918), and ADR 0021 and ADR 0022 do not link to each other (#4617).

This change is bookkeeping. It changes no decision.

## What Changes

- `docs/adr/README.md` gives the rules of a record: its scope, the MADR 4 front matter, the approval by the merge of the owner, the frozen body of an accepted record, the form of a Status History line, the supersession in both directions, the limits of length of a new record, the form of the Considered Options and the Confirmation sections, and the merge of record changes one at a time. It holds the MADR 4 template and an index that `devops docs generate` writes from the front matter.
- Each record 0001 to 0025 gets a front matter with `status`, `date`, `decision-makers`, `issue`, `tracker`, `supersedes`, `superseded-by`, `amends`, `amended-by` and `body-hash`. Its notes at the top and its `## Status` section move word for word into a last section `## Status History`.
- Dated lines record the facts that are out of date in ADR 0001, 0006, 0007, 0008, 0009, 0015, 0017, 0021, 0022, 0023, 0024 and 0025. ADR 0003 becomes superseded by ADR 0017 and ADR 0021, which hold its rules. ADR 0002, ADR 0011 and ADR 0012 stay superseded.
- `adr.py` reads the front matter with the `front_matter` plugin of mdit-py-plugins and `yaml.safe_load`, and the three patterns go. An entry of the request names the records that amend the record, and no status prose.
- `src/devops_cli/docs/adr_records.py` gives the body hash, the index and the problems of each record. `tests/invariants/test_adr_records.py` fails on a record with no status, a link in one direction only, a link to a missing record, an edit of an accepted body, a new record over the limits of length, and an index that is out of date.
- The scope `adr` is in `.github/labels.yml` and in the scopes of `.github/workflows/pr-title.yml`. `zensical.toml` gives a title to each status, and `overrides/main.html` gives each status an icon of the theme.
- mdit-py-plugins moves from the dev group to the runtime dependencies, because `src/` now imports it.

The change alters a behavior that a consumer observes, the ADRs that the alternatives check reads, so it carries a delta of the `roadmap-alternatives` spec. It fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-alternatives`: the check reads the status of an ADR from its front matter, keeps only the ADRs in force, and names the amending ADRs in each entry.

## Impact

- The alternatives check gets 7,355 tokens of decisions from 21 records in force, against 8,464 tokens from 22 records before. It keeps every record in force, and ADR 0001 is in the request again. ADR 0003 is superseded, so it is no longer in force.
- The change of the entries changes `adr_hash`, so each checked item becomes due again one time. The tracker merges every pure status change in this one pull request for that reason.
- Every later pull request that changes `docs/adr/` keeps the rules of the README, and the invariant test enforces them.

## Feasibility

- The parser: `uv run python` with markdown-it-py 4.3.0 and mdit-py-plugins 0.7.0 (both pinned in `uv.lock`) gives a first token `front_matter` with the YAML text and the line map `[0, 4]` for a four-line front matter. PyYAML 6.0.3 reads the text. YAML 1.1 reads an unquoted `0017` as the octal 15, so the model asks for quoted record numbers.
- The measure: the code of `origin/main` at 0a14161ed over the records of `origin/main` gives 22 records in force and 8,464 tokens (`count_tokens`), and `fit_to_budget` leaves out ADR 0003 and ADR 0001. The code and the records of this change give 21 records in force and 7,355 tokens, and `fit_to_budget` keeps all of them.
- The words: the 25 records held 66,340 words. Their bodies hold 63,542 words, and the Status History sections hold the other 2,798 words word for word, with 250 words of new dated lines. A script checked each moved note against the original text.
- The facts of the dated lines: `git log` gives the deletion of `docs/ROADMAP.md` and the `issues`-only consumer in #1952 and the in-place edit of ADR 0007 in #5110. `k8s/argocd/apps/argo-workflows.yaml` pins chart 2.0.18 and `k8s/argo-workflows/values.yaml` image v4.1.6 (ADR 0008 names 2.0.13 and v4.1.5). `k8s/devops/roadmap-service/deployment.yaml` sets 1 replica (ADR 0008, 0009 and 0015 name 0). The release notes of githubkit v0.17.0 (2026-10-28) say that githubkit prefers HTTPX2 when it is installed. Pull request #5183 moved the docs site to Zensical.
- The site: `uv run devops docs site build --strict` builds 109 pages with no issue, and the nav shows 21 accepted and 4 superseded records.

## Existing Tool Considered

MADR 4 gives the template and the front matter keys `status`, `date`, `decision-makers`, `consulted` and `informed`. The `front_matter` plugin of mdit-py-plugins and PyYAML read the front matter, and pydantic validates it. adr-tools (`generate toc`) and Log4brains read the status from a Markdown section or their own front matter, but neither keeps a hash of a body or checks a link in both directions. So the change builds the index, the body hash and the link check: about 0.5 M tokens to build, about 20k tokens a year to keep and about 30k tokens to fix until stable, and about 3 hours elapsed. The test runs in the static rows in less than 1 second.

The change deletes `_STATUS_VERB`, `_SUPERSEDED_BY`, `_SUPERSEDES`, `_ADR_REFERENCE`, `_plain`, `_title_and_status` and `_superseded` of `adr.py`.
