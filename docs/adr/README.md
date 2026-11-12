# Architecture decision records

This folder holds the architecture decision records of devops-cli. Each record holds one decision in the [MADR 4](https://adr.github.io/madr/) form. The alternatives check of the roadmap reads the records in force (`src/devops_cli/roadmap/adr.py`). `tests/invariants/test_adr_records.py` fails when a record breaks a rule of this page.

## When to write a record

Write a record for a choice that is difficult to reverse:

- A structure of the code or of the system.
- A quality attribute, such as security, cost or speed.
- A dependency or a tool.
- An interface.
- A process.

A value, a permission, a table row, a timeout or a rename is not a record. Write it in the OpenSpec change, in its spec and in the issue.

## Front matter

Each record starts with a YAML front matter. MADR 4 defines `status`, `date`, `decision-makers`, `consulted` and `informed`. The project adds the other keys. A key that has no value is not written.

| Key | Value |
| :--- | :--- |
| `status` | `proposed`, `accepted`, `rejected`, `deprecated` or `superseded`. |
| `date` | The date of the decision, as `YYYY-MM-DD`. |
| `decision-makers` | Roles only, such as `[owner]`. Never the name of a person. |
| `issue` | The number of the issue that asked for the decision. |
| `tracker` | The number of the tracker issue of the items that build the decision. |
| `supersedes`, `superseded-by` | The numbers of other records, each as a quoted string of four digits: `["0017"]`. |
| `amends`, `amended-by` | The numbers of other records, in the same form. |
| `body-hash` | The SHA-256 of the body. An accepted record has it. |

Write each record number in quotes. YAML reads an unquoted `0017` as the octal number 15, so the test refuses it.

The alternatives check reads only the records in force: a record with `status: accepted` that no record supersedes.

## Approval

1. An agent writes a new record with `status: proposed` and `decision-makers: [owner]`, in a draft pull request.
2. When the checks pass, the agent sets `status: accepted` and `body-hash`, and marks the pull request ready. `uv run devops ci test tests/invariants/test_adr_records.py` gives the hash of the body when the front matter has none.
3. The merge by the owner accepts the record. Only a person merges, so each accepted record on `main` has the approval of the owner. When the owner refuses the record, the pull request closes with no merge.

## An accepted record does not change

The body of a record is its text after the front matter, with no `Status History` section. After acceptance, a pull request changes an accepted or a superseded record only in these ways:

- It changes a status key of the front matter: `status`, `superseded-by` or `amended-by`.
- It adds one dated line at the end of the `Status History` section.
- It fixes the target of a broken link.

The test calculates the hash of the body again, with no link target, and fails when it is not `body-hash`. So an edit of the body in place fails. An agent never edits the body of an accepted record.

## Status History

`## Status History` is the last section of a record. A record gets it with its first line. When a pull request makes a fact of a record wrong, the same pull request adds the line (AGENTS.md rule 8). Each line has 30 words or fewer after its date, in one of these forms:

- `YYYY-MM-DD: Amended by ADR NNNN, section S.`
- `YYYY-MM-DD: Amended by the owner decision in #N, section S.`
- `YYYY-MM-DD: Superseded by ADR NNNN.`
- `YYYY-MM-DD: Fact out of date: <what> (#N).`
- `YYYY-MM-DD: Living detail moved to <path> (#N).`

The notes and the Status sections that the records held before 2026-11-12 are in this section word for word, before the dated lines.

## Supersede a record

- The new record sets `supersedes`. The same pull request sets `status: superseded` and `superseded-by` on the old record, and adds its `Superseded by` line. The test fails on a link that goes in one direction only, and on a link to a record that does not exist.
- The alternatives check does not read a superseded record. So the new record writes again each rule and each rejected option of the old record that stays in force.
- Do not amend a superseded record.
- After the third amendment of a record, or when its body contradicts the code, the next change supersedes the record.
- Code, tests and workflows cite the record in force. The pull request that supersedes a record moves the citations of the old record in `src/`, `tests/` and `.github/`. The archived OpenSpec changes and `CHANGELOG.md` are history, and they keep their citations.
- A sweep that renames a term does not change `docs/adr/`.

## Length

A record after ADR 0025 has a body of 1,000 words or fewer, a title of 10 words or fewer and a slug of 60 characters or fewer. The test fails when a record breaks a limit. Put designs, catalogues, row tables, cutover plans, caps and measurements in the OpenSpec change and its spec, in a setting or in a document, and link them under More Information.

A new record must also fit in the tokens that the records it supersedes make free. The alternatives check sends at most 8,192 tokens of decisions (`CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS`), and it leaves out the oldest records that do not fit. Short option bullets keep the budget.

## Considered Options and Confirmation

A record has one `Considered Options` section. Each option is a bullet that ends in one of these forms:

- `chosen.`
- `rejected, because <reason>.`
- `deferred until <condition>.`

The alternatives check reads this section. It reads an option that says `rejected` as a tool that the project refused. An option that says `deferred` refuses no tool, so the check stops a refusal when the premise changes.

A record has a `Confirmation` section. It names the test, the CI row or the metric that shows that the code keeps the decision.

## Merge record changes one at a time

Each change of a record in force changes the hash of the decisions that the alternatives check reads (`adr_hash` of `src/devops_cli/roadmap/alternatives.py`), and each checked item becomes due again. So one pull request changes the status keys of many records at one time, and the pull requests of new records merge one at a time, in the order of their tracker.

## Template

```markdown
---
status: proposed
date: YYYY-MM-DD
decision-makers: [owner]
issue: N
supersedes: ["NNNN"]
---

# Title of 10 words or fewer

## Context and Problem Statement

The problem in two or three sentences, with its evidence.

## Decision Drivers

- A driver.

## Considered Options

- **Option 1**: chosen.
- **Option 2**: rejected, because <reason>.
- **Option 3**: deferred until <condition>.

## Decision Outcome

Chosen option: "Option 1", because <reason>.

### Consequences

- Good, because <reason>.
- Bad, because <reason>.

### Confirmation

The test, the CI row or the metric that shows that the code keeps the decision.

## More Information

The links to the OpenSpec change, the spec, the settings and the issue.
```

## Index

`uv run devops docs generate` writes this table from the front matter of each record, and `uv run devops docs check` fails when the table is out of date.

<!-- ADR_INDEX_START -->

| Record | Title | Status | Date | Links |
| :--- | :--- | :--- | :--- | :--- |
| [0001](0001-github-is-the-roadmap-source.md) | GitHub is the roadmap's source of truth | accepted | 2026-10-01 | amended by 0012, 0016 |
| [0002](0002-roadmap-jobs-act-as-a-machine-account.md) | Roadmap jobs act as a machine account with a classic token | superseded | 2026-10-01 | superseded by 0015; amended by 0016 |
| [0003](0003-polling-is-how-the-roadmap-sees-changes.md) | Polling is how the roadmap sees changes; webhooks only cut latency | superseded | 2026-10-01 | superseded by 0017, 0021; amended by 0016 |
| [0004](0004-ci-is-the-authoritative-gate.md) | CI is the authoritative quality gate for merges into release and main | accepted | 2026-10-06 | amended by 0012, 0014 |
| [0005](0005-review-findings-come-from-tools-not-models.md) | Review findings come from tools and checked facts; models explain and plan | accepted | 2026-10-08 |  |
| [0006](0006-github-session-requests-go-through-gidgethub.md) | The GitHub session sends its requests through gidgethub | accepted | 2026-10-20 |  |
| [0007](0007-tests-double-only-process-edges.md) | Tests double only process edges, through seams | accepted | 2026-10-20 |  |
| [0008](0008-argo-workflows-run-the-roadmap-jobs-after-a-measured-go.md) | Argo Workflows runs the roadmap Service's queued and scheduled work, after a measured go | accepted | 2026-10-23 | amended by 0021 |
| [0009](0009-one-webhook-router-delivers-each-event-to-the-consumers-subscribed-to-it.md) | One webhook router verifies each sender its own way and delivers each event to the consumers subscribed to it | accepted | 2026-10-23 | amended by 0021 |
| [0010](0010-openspec-is-the-spec-and-change-proposal-layer.md) | OpenSpec is the spec and change-proposal layer | accepted | 2026-10-23 | amended by 0012 |
| [0011](0011-releases-come-from-trunk-towncrier-uv-and-semver-tags-instead-of-a-bespoke-cut.md) | Releases come from trunk, and towncrier, uv and semver tags replace the bespoke cut | superseded | 2026-10-23 | superseded by 0012 |
| [0012](0012-releases-are-derived-by-release-please-from-trunk-and-milestones-are-planning-buckets.md) | Releases are derived by release-please from trunk, and milestones are planning buckets | superseded | 2026-10-23 | supersedes 0011; superseded by 0013; amends 0001, 0004, 0010; amended by 0025 |
| [0013](0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md) | Releases use release-please as it ships, and agents stay out of them | accepted | 2026-10-23 | supersedes 0012 |
| [0014](0014-required-checks-gate-the-merge-and-the-pre-push-hook-runs-the-fast-static-checks.md) | The required checks of `main` gate the merge, and the pre-push hook runs only the fast static checks | accepted | 2026-10-24 | amends 0004 |
| [0015](0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md) | Roadmap jobs act as a GitHub App on the personal account | accepted | 2026-10-28 | supersedes 0002 |
| [0016](0016-labels-hold-the-roadmap-items-fields.md) | Labels hold the roadmap Item's fields, and no roadmap job reads or writes a project board | accepted | 2026-10-28 | amends 0001, 0002, 0003 |
| [0017](0017-each-subscribed-webhook-event-runs-the-update-scoped-to-it.md) | Each subscribed webhook event runs the update scoped to it, and the poll reconciles | accepted | 2026-10-28 | supersedes 0003; amended by 0021 |
| [0018](0018-a-sandboxed-read-only-run-tool-for-the-planner.md) | A sandboxed read-only run tool for the planner | accepted | 2026-11-07 |  |
| [0019](0019-a-decision-step-asks-jev-short-closed-questions-about-evidence-that-tools-extract.md) | A decision step asks Jev short closed questions about evidence that tools extract | accepted | 2026-11-09 | amended by 0020 |
| [0020](0020-a-decision-point-is-a-unit-of-a-workflow-with-a-resolver-chain-and-a-rule-goes-before-a-decision-model.md) | A decision point is a unit of a workflow with a resolver chain, and a rule goes before a decision model | accepted | 2026-11-10 | amends 0019; amended by 0023 |
| [0021](0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md) | The roadmap Service is a webhook router, cluster pods run the roadmap jobs, and Valkey holds their shared state | accepted | 2026-11-11 | supersedes 0003; amends 0008, 0009, 0017; amended by 0023 |
| [0022](0022-one-repository-reference-names-the-objects-labels-and-keys-of-each-repository.md) | One repository reference names the objects, labels and keys of each repository | accepted | 2026-11-11 | amended by 0023 |
| [0023](0023-the-project-brain-is-a-derived-index-in-two-cache-tiers-and-two-scheduled-runs-keep-it.md) | The project brain is a derived index in two cache tiers, and two scheduled runs keep it | accepted | 2026-11-11 | amends 0020, 0021, 0022; amended by 0025 |
| [0024](0024-the-project-owns-its-design-tokens-in-the-dtcg-format-and-style-dictionary-builds-them.md) | The project owns its design tokens in the DTCG format, and Style Dictionary builds them | accepted | 2026-11-12 |  |
| [0025](0025-generated-documents-stay-in-git-and-the-project-brain-cites-them.md) | Generated documents stay in git, and the project brain cites them | accepted | 2026-11-11 | amends 0012, 0023 |

<!-- ADR_INDEX_END -->
