# devops-cli

devops-cli automates DevOps work across the GitHub repositories it manages. This glossary holds the terms specific to that work.

## Planning and releases

**Roadmap**:
The items, the milestones a person plans them into, and the backlog, taken together. Labels and milestones on GitHub hold them (ADR 0016).
_Avoid_: plan, board

**Item**:
One unit of planned work on the roadmap, tracked as exactly one issue and delivered by exactly one pull request that delivers nothing else. An open issue becomes an item when intake places it on the roadmap: an item is an issue with a `priority/*` label. One label family holds each of its Status, Priority, Value and Effort.
_Avoid_: task, deliverable, card, ticket, work item, tracking issue

**Change**:
The in-repo plan and record of one item: the OpenSpec folder `openspec/changes/<issue>-<slug>/`, with its proposal, spec deltas, design and `tasks.md`, the checklist of the change. The pull request that delivers the item writes it and archives it into `openspec/changes/archive/` in its last commit.
_Avoid_: task file, change request, plan file

**Spec**:
The living specification of one capability, `openspec/specs/<capability>/spec.md`. Only `openspec archive` writes it, from the spec deltas of the change that it archives.
_Avoid_: requirements document, spec file

**Changelog line**:
The Conventional Commit title of a pull request into `main`. The squash commit takes it, and release-please writes it into `CHANGELOG.md` when its type is one that the changelog shows.
_Avoid_: changelog fragment, news fragment, changelog snippet

**Priority**:
An item's rank: P0 (critical), P1 (high), P2 (medium) or P3 (low).
_Avoid_: severity, category, priority category

**Value**:
How much delivering an item matters: high, medium or low.
_Avoid_: impact, benefit

**Effort**:
How much work an item takes: high, medium or low. Even a high-effort item fits in one pull request; anything bigger is split.
_Avoid_: size, estimate, story points

**New**:
An item that is not yet ready.
_Avoid_: backlog (as a status), todo, triage

**Ready**:
An item with a problem statement, acceptance criteria and an answer to every key question.
_Avoid_: refined, groomed

**Started**:
An item that is in progress, in review or done.
_Avoid_: active, claimed

**Blocked**:
An item waiting on something outside the roadmap, such as hardware, an upstream release or a person's decision. A blocked item is not started. A stop of the implement job also blocks an item, until a person comments `implement: retry`. The Service also clears a stop whose class a retry can fix. It continues a Job that has no result, within a limit. It also clears the stop when a new runner image rolls out (see docs/ROADMAP_WORKFLOW.md). Waiting on another item is a dependency, not blocked.
_Avoid_: on hold, waiting

**Dependency**:
An item that must be delivered before another item can be.
_Avoid_: blocker, blocked-by

**Not planned**:
An item closed without being delivered. It stays on record so the same idea is recognized as a duplicate if it surfaces again.
_Avoid_: rejected, won't fix, deferred

**Milestone**:
A planning bucket that a person sets on an issue, ordered by its due date. It never names a version, and no release reads it.
_Avoid_: release, sprint

**Backlog**:
The single prioritized pool of items in no milestone. Intake puts every new item there, and a person moves items from it into milestones.
_Avoid_: icebox, triage queue

**Critical fix**:
A P0 item that fixes a defect, a security advisory or a regression (a defect whose introducing commit is cited). Intake hands it to refinement at once.
_Avoid_: hotfix, P0 item

**Release**:
A version that release-please publishes when its release pull request merges. It ships every change merged into `main` since the last release.
_Avoid_: milestone, sprint, cut

**Release pull request**:
The one pull request that release-please opens and updates on `main`. It holds the next version and its changelog section, and the scheduled merge (every 6 hours, `release-merge.yml`) or a person merges it.
_Avoid_: cut PR, release branch

## Roadmap jobs

**Candidate**:
Something that surfaced (from a person, a review of merged code, an agent or discovery) and may become an item. An open issue with no `priority/*` label is a candidate: intake has not yet placed it on the roadmap, or a person took its priority off.
_Avoid_: proposal, suggestion

**Intake**:
The single entry point that turns a candidate into an item: it rejects duplicates, sets priority and puts the item in the backlog.
_Avoid_: ingestion

**Duplicate**:
A candidate that asks for the same change as an item: the same result and the same acceptance criteria, so that the delivery of one delivers the other. A shared theme, goal, umbrella or file does not make a duplicate. A candidate is never a duplicate of the issue that it is split from. It is also never a duplicate of an issue that has sub-issues, because the sub-issues deliver that issue.
_Avoid_: fold, overlap

**Related item**:
An item that shares a theme, a goal, an umbrella or a file with a candidate, but asks for a different change. Intake files the candidate and links the related item from its reason comment.
_Avoid_: near duplicate, similar item

**Discovery**:
Searching outside sources for candidates and handing them to intake.
_Avoid_: research

**Refinement**:
Answering an item's key questions until it is ready.
_Avoid_: grooming

**Alternative**:
An open, maintained tool or library that covers the need of an item, in whole or in part. The alternatives check looks for one, reads its license and its last activity, and records a verdict: covers, partly, none, not-applicable, rejected or in-use. Only the job gives not-applicable, for an item in a skip class (the type test, docs, refactor, chore, ci or perf, or a fix with a stack trace); every other item gets a verdict only after a search. The model can propose two more verdicts, and the job gives each one only when the text confirms it. The verdict rejected needs an ADR in force that rejected the tool and names it. The verdict in-use needs a title or a body that already names the tool. A person decides what an alternative means for the item: refinement asks a person to adopt a covering tool or to keep the item with a reason.
_Avoid_: competitor, substitute

**Staging**:
Making a Ready item Staged: a branch, an OpenSpec change in task groups that each fit one step, and a draft pull request that plans the item and closes no issue. The pull request has the type `docs(openspec)`, because a plan is no fix and adds no changelog line. The branch keeps the type of the issue. The planner reads the repository before it writes the plan: it has read-only tools (list files, read a file, search, git log and show, the symbols of a file, the callers of a symbol, a repository map and a base spec; with the toolset `extended` also the files that hold a name, and a read of an issue or a pull request and a search of open items on GitHub), and it works within a budget of tool calls and output tokens. The comment of the staged item reports the tool calls and the tokens of the plan run.
_Avoid_: scaffolding, pre-work

**Staged**:
A Ready item whose staging is done and whose staged branch is on `origin`. Its Status stays Ready until a person merges the plan, and then it is Planned. The draft pull request on its branch is the record.
_Avoid_: prepared, queued

**Planned**:
An item whose change folder `openspec/changes/<issue>-<slug>/` is on the default branch, and that has no branch on `origin`: a person merged the staging pull request. The Service sets its Status to Planned (`status/planned`) from its job record, as the single writer of that label: Ready until the plan merges, Planned after, and In Progress while a runner Job holds it. The runner Job sets In Review. It never changes a label that a person set. The stage job leaves it out, and also an item whose change is archived there. The implement job takes it: it makes the branch `<type>/<issue>-<slug>` at the default branch, with the slug of the folder, runs the groups that have an unticked task, and opens the draft pull request that closes the issue.
_Avoid_: merged plan, orphan

**Claim**:
The mark that says who works on an item now: one label of `owner/service`, `owner/agent` and `owner/human`. An item has at most one. Any actor may claim a free item with `devops roadmap claim`; `devops repos worktrees add` claims for an agent. A person's claim takes an item from the Service. The Service claims an item for the runner Job it creates, takes no item that an agent or a person holds, and releases its claim when the Job ends. A claim of an agent or a person ends a running Job at its next group boundary. No job removes such a claim.
_Avoid_: lock, assignment

**Step**:
The work of one task group of a staged change, sized so that its inputs fit a budget of tokens: the instructions of the group, the `AGENTS.md` of the repository and the routed sections of its documents, the item, the change folder and the packed files of the group.
_Avoid_: chunk, phase

**Draft readiness**:
The pure function that decides when any draft pull request is ready for review: stage plan, implement, agent or person. Completeness comes first (for an implement pull request, every task group ticked and the change archived), then passing checks, then any extra check. The implement job, the stage row and `devops pr ready` ask it.
_Avoid_: ready check, draft gate

**Decision point**:
A named place of a roadmap job where the job picks one band of a closed set: continue, review or flag. The registry holds each point with its fixed questions, its evidence builder, what each band does and its cuts file. A resolver chain answers it: a proven rule, then the decision model that `ai.decision_model` names, then the current behavior. Its mode in `roadmap.decisions` is off, shadow or on. A point returns a band and never a text (ADR 0020).
_Avoid_: gate, judge, pilot

**Implementing**:
Taking a Staged or Planned item to a ready pull request: one step for each task group that has an unticked task, the documentation, the archive, the push, the body that closes the issue, the watch of the checks, at most one fix step, draft readiness, and `gh pr ready`. A step may ask for a bounded change of its plan, or for a split when its inputs exceed the limit. A false premise returns the item to New with its evidence. The job ticks each task of a group whose exit checks pass, so a tick that the agent forgets does not stop the step. A step keeps each ticked task whose verification passes as a `wip:` commit that the job pushes, and a stop discards only the work after the last one. A stopped item is Blocked, names the work it kept, shows the masked diff of the work it discarded, and waits for the comment `implement: retry`. For a stop whose class a retry can fix, it waits for a continuation or a new runner image, within the limits of the Service. A person merges.
_Avoid_: building, executing

**Runner**:
The pod of a cluster Job in which the implement job runs its steps. The Service creates the Job from CronJob `devops-cli-runner`, for one Staged or Planned item, and creates no second Job for a repository while one runs. The shell of a step checks only the first word of a command and is no security boundary, so the runner is the sandbox: the pod has no Kubernetes token, the installation token of the job names one repository, the step's shell gets none of the job's variables, and the job process is not dumpable. The setting `roadmap.implement.in_runner` says a process is one.
_Avoid_: agent host, worker

**Unit of work**:
One pod that runs one roadmap job for one item, one issue or one batch of intake candidates (ADR 0021). Only the router and the sweep create a unit. The labels of its repository, its job and its item find it, so an item never gets a second unit. A unit judges its item again at its start, writes its marks and its failure entry, and writes no last success.
_Avoid_: task, worker, job (a job is what the unit runs)

**Sweep**:
The reconcile round that a cluster schedule starts every 5 minutes, and that the router or a due mark starts sooner (ADR 0021). It runs the short rows of each repository, creates a unit of work for each long row that has work and no unit, and writes the last success of each job. Until #4574 merges, the poll of the Service does this work.
_Avoid_: poll, tick, cron

**Due mark**:
A key in Valkey that makes a job of a repository due before its interval ends (ADR 0021). A unit of work that makes more work due sets it, as intake does for refine and refine does for stage. The router sets it for a sweep that exists, and during a hold. The next sweep reads it and creates the unit. A due mark has a TTL and is never the only copy of a decision.
_Avoid_: trigger, chain, flag

**Service**:
The long-running devops-cli deployment that runs the roadmap jobs when they are due, as found by webhook or by polling.
_Avoid_: runner, bot, daemon, worker

**Lane**:
One of the Service's three paths for a repository's jobs, each running one round at a time. The triage lane runs intake. The model lane runs refinement, the retitle job, staging and the alternatives check, which call a model; the retitle row calls the model of the triage task, and runs before the stage row, every 61 minutes, so the stage job reads the shortened titles. The status lane runs the metrics, implement, stage_ready, release_comments, github_status and cloudflare_status rows, which call no model; the stage_ready row marks a staged draft pull request ready when its checks have passed, and the release_comments row comments the version, and the time it runs, on the issues of a release, and the github_status and cloudflare_status rows each read one status page, so a failed read fails its own row. All three get every trigger, and a round in one never waits for a round in the others.
_Avoid_: queue, track, worker

## Code review

**Finding**:
A defect at a location in the reviewed commit, reported by one of these producers: a tool, an advisory, a confirmed version fact, a rule-pack rule or a replayed sandbox observation. It carries the anchor that shows where it came from.
_Avoid_: claim, issue, alert

**Anchor**:
The record that ties a finding to its producer: a tool run's result, an advisory, a fact, a rule-pack rule or a replayed observation.

**State**:
Open, suppressed, fixed or confirmed.
- Tool runs open and fix findings.
- Reviewed project configuration suppresses them.
- Only a person's valid verdict or a replayed observation confirms one.
_Avoid_: status, verdict

**Verdict**:
The decision on a finding: verified (the defect is there), invalidated (a false positive), mitigated (the defect is there, but a named guard in named files limits it) or unverified (no decision yet). It records who gave it: a check or a person; sessions saved before #1150 also record the verifier model or an agent.
_Avoid_: status, resolution

**Review session**:
One review run: what was reviewed, every finding it raised and their verdicts.
_Avoid_: review run, report

**Suppression**:
A rule, with a reason and an expiry, that hides a finding. It lives in project configuration read at the base revision, or in an inline marker that already exists at the base revision.
_Avoid_: known false positive, hallucination entry

**Coverage gap**:
A file a tool did not scan, or a reference item a review or model job needed and did not get, stated in the review.

**Lead**:
An unconfirmed suggestion from a model or a matcher. It is never a finding.

**Rule pack**:
devops-cli's own Semgrep rules. Each has passing `ruleid:`/`ok:` tests, and a rule joins only when a person merges it.

## Verification

**Gate**:
A binding condition that must pass before a pull request merges.
_Avoid_: quality gate, 7-gate, 10-gate, barrier, hurdle

**Check**:
An automated test, analysis step or verification job run against a commit or pull request.
_Avoid_: test run, task, action, status

**Required check**:
A check configured in repository rulesets that must complete with a passing status before a pull request can merge.
_Avoid_: mandatory check, blocking check, required status check

## Telemetry

**Breakdown panel**:
A timeseries panel that shows metrics divided by a dimension such as pod, container or deployment.
_Avoid_: multi-series graph, split graph

**Aggregate line**:
A reference line on a breakdown panel, labeled Total (Sum) or Average (Mean), that sums or averages the lines shown by the breakdown query.
_Avoid_: baseline line, summary series
