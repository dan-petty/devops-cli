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
An open, maintained tool or library that covers the need of an item, in whole or in part. The alternatives check looks for one, reads its license and its last activity, and records a verdict: covers, partly, none, not-applicable, rejected or in-use. Only the job gives not-applicable, for an item in a skip class (the type test, docs, refactor, chore, ci or perf, or a fix with a stack trace); every other item gets a verdict only after a search. The model can propose two more verdicts, and the job gives each one only when the text confirms it. The verdict rejected needs an ADR in force whose rejected options alone name the tool. The verdict in-use needs a title or a body that already names the tool, or the job gives it with no proposal when the repository already uses the tool: its SBOM, its deployed files or a package that deps.dev links to the tool. A person decides what an alternative means for the item: refinement asks a person to adopt a covering tool or to keep the item with a reason.
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
The work of one task group of a staged change, sized so that its inputs fit a budget of tokens: the instructions of the group, the `AGENTS.md` of the repository and the routed sections of its documents, the item, the change folder and the packed files of the group. A roadmap step is a different term.
_Avoid_: chunk, phase

**Draft readiness**:
The pure function that decides when any draft pull request is ready for review: stage plan, implement, agent or person. Completeness comes first (for an implement pull request, every task group ticked and the change archived), then passing checks, then any extra check. The implement job, the stage row and `devops pr ready` ask it.
_Avoid_: ready check, draft gate

**Decision point**:
A named place of a roadmap job where the job picks one band of a closed set: continue, review or flag. The registry holds each point with its fixed questions, its evidence builder, what each band does and its cuts file. A resolver chain answers it: a proven rule, then the decision model that `ai.decision_model` names, then the current behavior. Its mode in `roadmap.decisions` is off, shadow or on. A point returns a band and never a text (ADR 0020).
_Avoid_: gate, judge, pilot

**Job grade**:
The measured performance of one roadmap workflow, from the result line of each attempt in Loki: `100`, `90`, `80`, `70`, `60`, `<60` or `too few` under 30 attempts. It is the floor of the success ratio of the attempts with no infrastructure cut, and `100` when each attempt is a first pass. Each grade has one owner action ([docs/roadmap/job-success.md](docs/roadmap/job-success.md)). `devops roadmap eval grades` prints it. A job grade is not a band: a band is the answer of a decision point.
_Avoid_: band, score, SLO

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

**Roadmap step**:
One part of a roadmap job that runs the same way each time, such as `push`, `open`, `watch`, `ready`, `fix-checks` and `fix-conflict` (ADR 0021 section 8). Each is one module and one command of the group that ADR 0021 section 8 names, and every caller uses it. It writes one JSON result line, exits 0 (done, or nothing to do), 1 (a typed stop) or 75 (try again later), and sends no request with `--dry-run`. GitHub state is its first marker, so a second run changes nothing.
_Avoid_: step alone (a step is the work of one task group), action, task

**Step job**:
A unit of work whose pod runs one roadmap step alone for one pull request: `fix-checks` or `fix-conflict` (ADR 0021 section 8). The sweep creates it from the due mark that `watch` sets. A short roadmap step, such as `watch` or `ready`, is no step job: it runs in the sweep, because a pod for each tick costs more than the work. `push` and `open` run inside the unit of their producer.
_Avoid_: fix job, step pod

**Branch run**:
One of the runs of one roadmap job for one item. A job has one branch run by default, on the base branch `<type>/<issue>-<slug>`, with no judge. With more than one, the runs work at the same time, each on its branch `<type>/<issue>-<slug>-<n>`, with no pull request. A judge then writes one result to the base branch and its one pull request (#5474, [docs/AGENTIC_WORKFLOWS.md](docs/AGENTIC_WORKFLOWS.md#the-job-model)).
_Avoid_: candidate (a candidate is an issue that intake has not placed), variant

**Project brain**:
The index of what the alternatives checks found, with the caches of the GitHub answers, the tool facts and the documents that they read (ADR 0023, ADR 0025). The check of one item reads a digest of it before its model call. Two scheduled runs, `brain-daily` and `brain-weekly`, keep it. Valkey holds it. Each entry is derived and has a durable copy: the block of its item, a hidden block on the tracker issue of its repository, or the document on `main` that its citation names. The brain never holds the only copy of a fact.
_Avoid_: memory, knowledge base (the knowledge base is the reference corpus of the AI commands)

**Citation**:
The pointer from a brain entry to the document text that supports it (ADR 0025): the path, a first-parent commit of `main`, the lines, a hash of the span, the class of the document in the docs inventory and the date of the commit. A generated document adds its source, and an ADR adds its status. A citation is stale when the text at the head commit no longer has the hash.
_Avoid_: reference, link, source (the source is the document that the citation names)

**Service**:
The long-running devops-cli deployment that runs the roadmap jobs when they are due, as found by webhook or by polling.
_Avoid_: runner, bot, daemon, worker

**Lane**:
One worker of the Service with its trigger queue, its clone and its listing snapshot, for each repository. It runs one round at a time. Each row of the due table has a lane of its own, named after the row, unless the setting `service.lanes` puts rows into a shared lane. Lanes do not wait for each other. [docs/CLUSTER.md](docs/CLUSTER.md#roadmap-service), Roadmap service step 17, tells how.
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

**Generated document**:
A document that `DocGenerator` or the instruction generator writes: a document of class `generated` in the docs inventory (ADR 0025), such as `docs/CLI_REFERENCE.md`, which holds the command matrix. It stays in git. The pull request that changes its source regenerates it, and the `docs` row of `Static Analysis` refuses it when it is not the output of its generator. Nobody edits it by hand.
_Avoid_: reference doc, build output, artifact

## Telemetry

**Breakdown panel**:
A timeseries panel that shows metrics divided by a dimension such as pod, container or deployment.
_Avoid_: multi-series graph, split graph

**Aggregate line**:
A reference line on a breakdown panel, labeled Total (Sum) or Average (Mean), that sums or averages the lines shown by the breakdown query.
_Avoid_: baseline line, summary series

## Infrastructure

**Infra repo**:
A git repository with an Ansible inventory, its playbooks and roles, which `devops infra` manages. The setting `infra.repos` names each infra repo, its checkout and its agent access level. A command reads an infra repo at a commit that `origin` holds, by default the head of its default branch, never in the working tree of the checkout. dan-petty/homelab is one.
_Avoid_: infra environment, inventory repo

**Agent access level**:
What an agent may do on the hosts of one infra repo: `none`, `plan`, `safe` or `full`. A repo with no level is at `none`. Only a person sets a level above `none`. It stops an agent error; it is not a security boundary.
_Avoid_: approval level, permission, trust level

**Infra plan**:
The record of one check-mode run of a playbook of an infra repo at one commit: for each host the changed tasks, the disruptive classes, the unchecked tasks and the changes with the diff hidden, and whether the run ended `ok` or `failed`. Its id is the SHA-256 of its facts, without the time. `devops infra plan` writes it under `<data dir>/infra/<owner>/<name>/plans/<id>/` with the runner artifacts. Only a plan that ended `ok` can be applied.
_Avoid_: dry run (a dry run makes no request), preview, check run

**Disruptive class**:
A change that takes a host out of service for a time, as the job events of a plan show it: `reboot`, `service-restart:<unit>` (a restart, reload or stop of a unit that `devops_infra_nondisruptive_units` does not list) or `drain`.
_Avoid_: risky change, outage

**Unchecked task**:
A task that check mode skipped, such as a `command` with no `creates` or `removes`, so the plan does not show what it does in an apply. A task that a false `when` skipped is not unchecked.
_Avoid_: skipped task

**Infra apply**:
The run of a saved infra plan on the hosts of an infra repo with `devops infra apply`, at the commit of the plan. The hosts with no disruptive class run together. Each disruptive host runs alone in plan order: drain check, drain, fresh check, run, Ready, the health of the nodes, uncordon only when the node was schedulable before, and the critical alerts. The first failure stops it. Each apply writes one audit record, `infra.apply`.
_Avoid_: deploy, rollout, make target

**Fresh check**:
The check-mode run of one disruptive host after its drain and before its run in an infra apply. It must show the plan of the host again, else the apply stops before the host changes.
_Avoid_: re-plan, second plan

**Drain check**:
`kubectl drain --dry-run=server` of a node before its drain. The API server checks each eviction against the PodDisruptionBudgets and changes nothing, so a drain that a budget blocks stops the apply before the node is cordoned.
_Avoid_: pre-drain, drain test

**Project profile**:
The facts of one repository that devops-cli reads: its type and the layout of its files. They merge from the field defaults, the type template in `src/devops_cli/templates/profiles/`, detection in the files of the repository and its own `.devops/project.toml`, and each value records its source. The config of devops-cli holds operational keys only, never a fact of a project.
_Avoid_: project config, repo settings, manifest

**Environment tree**:
The Kubernetes folder of an infra repo: what one cluster runs, such as its Argo CD Applications, the values of its charts and its dashboards. A command takes its root from `--k8s-dir`, else from the profile fact `kubernetes.dir` of the repository of the current folder, else of the one infra repo that gives it. The product base `k8s/devops`, which devops-cli ships, is not part of it.
_Avoid_: homelab config
