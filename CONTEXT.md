# devops-cli

devops-cli automates DevOps work across the GitHub repositories it manages. This glossary holds the terms specific to that work.

## Release planning

**Roadmap**:
The current release, the planned releases and the backlog, taken together.
_Avoid_: plan, board

**Item**:
One unit of planned work on the roadmap, tracked as exactly one issue and delivered by exactly one pull request that delivers nothing else. An open issue becomes an item when intake places it on the roadmap.
_Avoid_: task, deliverable, card, ticket, work item, tracking issue

**Task file**:
The in-repo implementation record of one item, written in the pull request that delivers it.
_Avoid_: task, task item

**Changelog fragment**:
One item's changelog entries, written as `changelog.d/<issue>.md` in the pull request that delivers it and collected into the release's section of `CHANGELOG.md` by the cut commit, which deletes it. A critical fix after the cut writes its entry in that section instead, with no fragment.
_Avoid_: news fragment, changelog snippet

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

**Stalled**:
An in-progress item with no commits, pull request activity or status change for the configured stall window. It is treated as not started again, so it can be descoped. An item in review never stalls.
_Avoid_: stale, abandoned

**Blocked**:
An item waiting on something outside the roadmap, such as hardware, an upstream release or a person's decision. A blocked item is not started and cannot join a starting release. Waiting on another item is a dependency, not blocked.
_Avoid_: on hold, waiting

**Dependency**:
An item that must be delivered before another item can be.
_Avoid_: blocker, blocked-by

**Not planned**:
An item closed without being delivered. It stays on record so the same idea is recognized as a duplicate if it surfaces again.
_Avoid_: rejected, won't fix, deferred

**Release**:
A numbered version that ships a fixed set of items.
_Avoid_: milestone, sprint

**Current release**:
The one release being worked toward now: the lowest-numbered release that hasn't shipped. Its scope is fixed when work on it starts; after that, only a critical fix can join it on the jobs' own placement, and an item a person places in it stays with a comment naming the rule it breaks.
_Avoid_: active milestone, air-locked milestone

**Planned release**:
A later release whose scope is tentative and can be reshuffled freely until it becomes the current release.
_Avoid_: scheduled milestone, future milestone

**Release growth**:
The items that joined a release after its start, were turned away, descoped or trimmed, as the job's tally counts them.


**Backlog**:
The single prioritized pool of items not assigned to any release. Every open P0 and P1 item sits in an open release; only items a person took out of a release stay in the backlog.
_Avoid_: icebox, triage queue

**Critical fix**:
A P0 item that fixes a defect, a security advisory or a regression (a defect whose introducing commit is cited). It is the only kind of item that can join the current release after it starts; a P0 feature waits for the next release instead.
_Avoid_: hotfix, P0 item

**Descope**:
To move an item that hasn't started out of the current release into the next planned release.
_Avoid_: rollover, defer

**Cut**:
Opening a release's pull request. A critical fix still joins the release until that pull request merges; after that, it goes first into the next release. Closing that pull request without merging it un-cuts the release.
_Avoid_: freeze, air-lock

**Ship**:
A release ships when its pull request merges and it is published; the next release starts at that moment.
_Avoid_: publish, deliver

## Roadmap jobs

**Candidate**:
Something that surfaced (from a person, a review of merged code, an agent or discovery) and may become an item. An open issue that intake has not yet placed on the roadmap, or whose card a person archived, is a candidate.
_Avoid_: proposal, suggestion

**Intake**:
The single entry point that turns a candidate into an item: it rejects duplicates, sets priority and places the item.
_Avoid_: ingestion, triage

**Discovery**:
Searching outside sources for candidates and handing them to intake.
_Avoid_: research

**Refinement**:
Answering an item's key questions until it is ready.
_Avoid_: grooming, triage

**Reprioritization**:
Re-ranking items, placing open P0 and P1 items from the backlog into open planned releases, moving items between planned releases and the backlog, starting each release by filling it to size, and holding the current release to its admission rule and its limit, its size plus a few slots, so that a late P0 or P1 item joins without moving another out. A person's ranking and placement stand: an item a person places in a release stays there, and the jobs comment on a rule it breaks rather than moving it out. The admission rule and the cut bind everyone else, and the merged release's lock binds everyone.
_Avoid_: guard, governor, scope governor

**Closure**:
Closing a delivered item with a summary of what changed, and cutting a release, with its changelog, once every item in it is closed or descoped.
_Avoid_: completion, wrap-up

**Service**:
The long-running devops-cli deployment that runs the roadmap jobs when they are due, as found by webhook or by polling.
_Avoid_: runner, bot, daemon, worker

**Lane**:
One of the Service's two paths for a repository's jobs, each running one round at a time: the release lane runs closure, reprioritization and the metrics, and the model lane runs intake and refinement, which call the model. Both get every trigger, and a round in one never waits for a round in the other.
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
A binding condition that must pass before code merges or a release advances.
_Avoid_: quality gate, 7-gate, 10-gate, barrier, hurdle

**Check**:
An automated test, analysis step or verification job run against a commit or pull request.
_Avoid_: test run, task, action, status

**Required check**:
A check configured in repository rulesets that must complete with a passing status before a pull request can merge.
_Avoid_: mandatory check, blocking check, required status check
