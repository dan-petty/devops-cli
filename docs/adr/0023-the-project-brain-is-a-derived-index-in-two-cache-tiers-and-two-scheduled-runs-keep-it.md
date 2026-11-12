---
status: accepted
date: 2026-11-11
decision-makers: [owner]
issue: 4625
tracker: 4624
amends: ["0020", "0021", "0022"]
amended-by: ["0025"]
body-hash: 5813f875663094d27ebdd5ee30e3cb8e6398a344852204fd325564628d8967cd
---

# The project brain is a derived index in two cache tiers, and two scheduled runs keep it

The alternatives check judges one item at a time. It does not see the tools that the project uses, the verdicts of near items or the ADRs that changed after its verdict. The project brain is an index of what the checks found, with caches of the GitHub answers and tool facts that they read. This record sets the tiers and the data classes, with the durable copy of each class. It also sets the two runs that keep the index, the canonical tool id and three decision points. Tracker #4624 holds the items that build it.

## Context

Facts measured on 2026-11-11, recorded on tracker #4624:

- **The check does not see the tools in use.** 58 of 97 verdicts `covers` or `partly` named a tool that the project already uses. 1 of 5 verdicts `rejected` is false: #3258 says that ADR 0010 rejects OpenSpec, but ADR 0010 adopts it.
- **One tool has many names.** 88 tool strings name 81 tools.
- **The project view is missing.** 19 tools on 2 or more items cover 68 items. 8 need areas got different tools for one need. Two verdicts conflict with an ADR in force (#3064 with ADR 0008, #3258 with ADR 0010).
- **The listing reads cost requests.** The rows `other` and `intake` of the Service sent 27,138 GitHub requests in 24 hours. Only the CLI intake reads through the listing snapshot of #4552.
- **No durable home for derived data.** No Valkey instance has a backup off its node. The consolidate plan of 2026-11-10 is a local file with no copy.
- **ADR 0021 lists schedules only for the metrics row and the sweep.** It has no row for a run that keeps project data.

## Decision

### 1. The check of one item reads project context

The alternatives check of one item stays the main path. Before its one model call it reads three things:

- **The tools in use.** The SPDX export of the GitHub dependency graph gives the package and action purls. A `git grep` of the deployed paths (`k8s/`, `tf/`, `.devcontainer/`, `tools.lock`) gives the services and the command-line tools.
- **The digest of the brain.** At most 2,000 tokens, and each fact has its date. It holds the near items and their verdicts, the canonical tools and their rings, the ADR status of each tool and the area verdict.
- **The ADR index at the head commit**, as today.

Two code rules then apply. A tool with the verdict `covers` or `partly` that the project uses becomes `in-use`. The verdict `rejected` needs an ADR in force that names the tool under a rejected option. The check adds no generative call.

Valkey can be slow or down, the index can be missing, or the run can be on a workstation. Then the digest is empty and the check runs as before.

An area check runs the alternatives agent once for a need area of 2 or more open items with different tools. At most 5 area checks run in a week. Its verdict goes to the insight and to the digest of each member. It never writes the block of a member, and it does not replace the check of one item.

### 2. Two tiers

| Tier | Stores | Where |
| :--- | :--- | :--- |
| Local | The in-process stores, the file listing snapshot (#4552), the embedding disk cache (#4546) | Each process. A workstation has the local tier only. |
| Shared | `valkey-devops` for the caches, and `valkey-roadmap` for the brain index | The cluster. Each process has one client behind a circuit breaker (pybreaker). |

- **Read, content-addressed data** (tool facts, searches, pages, the inventory, embeddings): memory, then Valkey, then disk, then the source. A hit in a lower tier fills the tiers above it.
- **Read, the listing snapshot:** the reader loads the local and the shared copy. It drops a copy with another schema, or a copy whose last full read is older than 24 hours. It takes the newer watermark and reads the changes since it.
- **Read, the brain index:** `valkey-roadmap` only. When the index is missing, the reader uses the empty digest.
- **Write:** the source first, then the durable copy on GitHub for derived data, then Valkey, then the local tier. A failed Valkey write is a later miss, never a job error. A value over 1 MiB stays local.
- **Slow or down:** a connect waits at most 0.25 seconds and a command 2 seconds. One failure opens the breaker for 60 seconds. While it is open, each read is a miss and each write is skipped and counted.
- **Timeouts:** each bound is shorter than the bound of the call around it. The reference step (120 s) is shorter than the deadline of the alternatives unit (3,600 s). A Valkey command (2 s) and a GitHub read (60 s, #4626) are shorter than the reference step.
- **The stored GitHub answers** (gidgethub `cache=`) stay in the process. A shared store of them comes only if the two-token probe of ADR 0021 section 6 passes. The cache of `run_gh` output stays local always, because it answers with no request, so GitHub does not check the token.

### 3. Data classes and their durable copies

Valkey never holds the only copy of a decision (ADR 0021 rule 1). Each class has a durable copy.

| Class | Entries | Durable copy | Rebuild |
| :--- | :--- | :--- | :--- |
| C, caches | The listing snapshot, tool facts, searches, pages, the inventory, embeddings | The source | Read the source again. A loss costs requests or embedding calls. |
| S, index | `brain-item`, `brain-tool`, `brain-ref` | The alternatives block and the job record of each item | Repair parses the blocks from the snapshot, with no model call. |
| D, insights | Insights, scores, rings, area verdicts, fact values | One hidden block for each changed insight, in the run comments on the tracker issue | Repair reads the comments. The newest version of each insight wins. |

- **The tracker issue.** One for each repository, with the label `type/epic` and a marker. Repair creates it once, and it reads the marker first (ADR 0021 rule 5). Its body is a view for people and is never parsed for a rebuild. Each job selection skips it.
- **A run comment** holds at most 40 blocks, and a repository gets at most 2 run comments a day.
- **A gauge counts the undurable insights:** an insight whose version is newer than the version in the last comment. An alert fires when it stays above 0 for 26 hours.
- **An accepted insight** becomes a normal issue through intake, at most 2 a week. A proposed ADR change goes as a `docs(adr)` issue. No brain job writes a label, a milestone, a release or an ADR file.
- **Keys.** The brain keys use the forms of ADR 0022 section 5: `roadmap:v1:brain-<kind>:<owner>/<name>[:<id>]`. Each key has a TTL or one owner (ADR 0021 rule 6). An insight never joins the items of two repositories.

### 4. Two scheduled runs keep the brain

| Run | Tasks | Schedule |
| :--- | :--- | :--- |
| `brain-daily` | repair, signals, consolidate, evaluate | `30 2 * * *` (UTC) |
| `brain-weekly` | aggregate, improve | `0 1 * * 1` (UTC) |

- **The engine parts.** One WorkflowTemplate `roadmap-brain` in namespace `devops`, and two CronWorkflows with `schedules`, `concurrencyPolicy: Forbid` and the mutex `brain`. One pod runs all tasks of one run, for each repository of the brain in turn. `retryStrategy` retries exit 75 only, never a refusal of a model.
- **The due marks.** `brain-repair` is set when the index marker is missing or has an old schema. `brain-consolidate` is set when a new canonical tool or reference comes. The sweep reads each mark and creates a run of that task only, at most once a day for each mark.
- **A CronWorkflow is not a unit,** as for the metrics row. The sweep creates the runs of the due marks, so the rule "Only the router and the sweep create units" stays.
- **Bounds.** Each task has a time budget, a cap of writes and a cap of spend. A daily run spends at most 0.10 USD, and a weekly run at most 0.50 USD. Improve makes at most 5 area checks and 2 proposals a week. The first 2 weekly runs only plan, and file nothing.
- **Audit.** Each change writes one JSON log line and a counter, and adds one entry to the stream `brain-events`. The stream is an audit trail only, never a trigger queue. A run that changed something writes one summary comment on the tracker issue.
- **Safe stop.** Each change is one `WATCH`/`MULTI`/`EXEC` transaction. A rebuild writes a temporary key and renames it. On `SIGTERM` the task stops between two transactions and exits 0. So each entry is whole, old or new.
- **Before the engine step (#4566),** a person or an agent can run the same commands on a workstation. They write only to GitHub. `--dry-run` sends no request.

### 5. The Service row `brain`

The row `brain` joins the rows of ADR 0022 section 2. The template, its pods and its keys take the labels, the service name `roadmap-brain` and the key forms of ADR 0022. A brain run has no item, so its unit name has no `-<n>`.

### 6. The canonical tool id

Each tool has one canonical id: a purl, `pkg:pypi/<name>` with the name from `packaging.utils.canonicalize_name`, or `pkg:github/<owner>/<repo>`. A tool that has no purl takes its deps.dev project key. The names that the checks wrote stay as aliases of the id. The key id of a tool is a hash of its canonical id.

### 7. Three decision points

Each point follows ADR 0020 and rules 4, 6 and 7 of ADR 0019. Each starts in `shadow` and stays there until a fit and a person turn it on. Each has the resolver chain model and fallback: a rule resolver comes only when a rule meets the bar on labelled data. The fallback is the deterministic step of today. The counter of ADR 0020 section 7 gets 8 series for each point, 24 in total.

| Point | Question | Evidence | Fallback | Bands |
| :--- | :--- | :--- | :--- | :--- |
| `brain.reference_relevance` | A `Noul` for each candidate file: does it implement the need of the item? | The need line, the path, the description and the license of the candidate, and the matched symbols, each cut to a limit | The gates (license, activity) and the rank pick at most 3 links | `continue` links the candidate. `review` leaves it out. `flag` leaves it out and logs it. |
| `brain.merge_same_need` | A `Noul` for each pair that the rules leave open: do the two entries name one need? | The two titles and need lines, the canonical ids and the overlap of the members | The pair stays apart | `continue` keeps the pair apart. `review` sends it to the consolidate judge. `flag` also logs it. |
| `brain.entry_quality` | A `Score` for each insight on a rubric of support, freshness and use | Counts: members, open members, uses in 30 days, the age of the newest source, the ADR status of the tool | A fixed sum of the same features marks an insight stale or weak | `continue` keeps the state of the fixed sum. `review` sends the insight to the next improve run. `flag` also logs it. |

| Point | Labels | Bar for `on` |
| :--- | :--- | :--- |
| `brain.reference_relevance` | The links that a person labels, and the links that repair finds dead | At least 30 links in `continue` with no bad label. `review` holds at least 20 percent of the links that the fallback makes and a person labels bad. |
| `brain.merge_same_need` | The result of the consolidate judge, and the groups that a person applies with `consolidate --apply` | At least 30 pairs in `continue` that the judge and the person keep apart, with none that they merge. `continue` holds at least 10 percent of the open pairs. |
| `brain.entry_quality` | The later state of the insight: a person accepts or declines its proposal, or its members close | At least 30 insights in `continue` whose later state agrees with the fixed sum. `review` holds at least 20 percent of the insights that a person declines. |

- **The bars.** No loss in 30 cases gives a loss rate under 10 percent with 95 percent confidence (the rule of three). A bar above the oracle of the labelled data is not set (ADR 0020 section 8).
- **A private repository.** Its digest holds counts only (ADR 0020 section 1), so `brain.reference_relevance` and `brain.merge_same_need` do not run for it.

### 8. Shared caches hold public repositories only, until role ACL users exist

`valkey-devops` has only the default user, and 2 of 7 repositories of the Service are private. Until `valkey-devops` has one ACL user for each role and the default user is off, the shared tier holds data of public repositories only. A private repository uses the local tier. For a private repository, the reference step uses the GitHub providers only, and grep.app and the web search stay off.

## Considered Options

- **An event stream with a fold:** rejected. A unit pod ends after its one event, and a workstation does not reach the cluster Valkey, so a spooled event is lost.
- **A radar file in git, written by a pull request after each run:** rejected. AGENTS.md rule 8 forbids a pull request that only updates tracking. Each push costs about 45 runner-minutes.
- **An area check that replaces the check of one item:** rejected. 62 of 81 tools are on one item only, so those items get no check.
- **A vector store for the entries:** rejected. 395 open items fit an in-memory cosine, as intake does.
- **One store for the #4582 read model and the listing snapshot:** rejected. The router user then reads private bodies in the state instance. They stay two keys with one writer.
- **The brain runs as rows of the sweep only:** rejected. The sweep (#4574) is the last step of #4517, and the brain needs only the engine (#4566).
- **hishel as the cache of GitHub answers:** rejected. GitHub answers are private and vary by token, and hishel 1.4.0 is a shared cache by default.

## Consequences

- Each item of tracker #4624 puts its spec delta in a nested capability `openspec/specs/project-brain/<area>/spec.md`, the layout of #4622 that openspec 1.14.3 reads. No item adds a requirement to `openspec/specs/roadmap-stage/spec.md`. The items that change `openspec/specs/roadmap-alternatives/spec.md` merge one after the other.
- The brain adds 8 pods a week, against the 7,000 to 8,400 of ADR 0021. Its spend is at most 1.20 USD a week, and an alert fires above 1 USD a day.
- The item of the shared tier raises the `maxmemory` of `valkey-devops` from 96 MB to 256 MB. The signals task needs a NetworkPolicy to Prometheus.
- #3670 makes the scoped intake and the intake of the Service read through the listing snapshot. That removes about 25,000 of the 27,138 requests a day.
- The counter of ADR 0020 section 7 has at most 84 series with the three points.
- A loss of `valkey-roadmap` costs a rebuild by repair, not a decision. While the index marker is missing, each check uses the empty digest.

## Status History

Amended on 2026-11-12 by [ADR 0025](0025-generated-documents-stay-in-git-and-the-project-brain-cites-them.md).

This record amends ADR 0020, ADR 0021 and ADR 0022, and it changes the scope that #2648 set. The Status section gives each change.

The merge of the pull request that adds this record is the approval of this record. `git log --follow -- docs/adr/0023-the-project-brain-is-a-derived-index-in-two-cache-tiers-and-two-scheduled-runs-keep-it.md` names the merge commit.

- **ADR 0021.** The unit table gets two rows, `brain-daily` and `brain-weekly`, in the form of the metrics row. The engine parts name their CronWorkflows. A CronWorkflow is not a unit, so the rule "Only the router and the sweep create units" stays as it is.
- **ADR 0022.** Section 2 gets the row `brain`.
- **ADR 0020.** The catalogue gets the three points of section 7. They are in this record, in the form of the catalogue.
- **#2648** (closed 2026-10-29) kept the alternatives check to one item, and called a check across items a different question. Section 1 changes that scope: the check of one item reads project context. The check of one item stays.

ADR 0001, ADR 0016 and the rules of ADR 0021 section 3 stay as they are. GitHub stays the source of truth.

2026-11-12: Living detail moved to tracker #4624: the items that build this record and their state (#5225).
