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
One item's changelog entries, written as `changelog.d/<issue>.md` in the pull request that delivers it and merged into the release's section of `CHANGELOG.md` at the cut.
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
The one release being worked toward now: the lowest-numbered release that hasn't shipped. Its scope is fixed when work on it starts; after that, only a critical fix can join it.
_Avoid_: active milestone, air-locked milestone

**Planned release**:
A later release whose scope is tentative and can be reshuffled freely until it becomes the current release.
_Avoid_: scheduled milestone, future milestone

**Backlog**:
The single prioritized pool of items not assigned to any release.
_Avoid_: icebox, triage queue

**Critical fix**:
A P0 item that fixes a defect, a security advisory or a regression (a defect whose introducing commit is cited). It is the only kind of item that can join the current release after it starts; a P0 feature waits for the next release instead.
_Avoid_: hotfix, P0 item

**Descope**:
To move an item that hasn't started out of the current release into the next planned release.
_Avoid_: rollover, defer

**Cut**:
Opening a release's pull request. From then on the release accepts no more items. Closing that pull request without merging it un-cuts the release.
_Avoid_: freeze, air-lock

**Ship**:
A release ships when its pull request merges and it is published; the next release starts at that moment.
_Avoid_: publish, deliver

## Roadmap jobs

**Candidate**:
Something that surfaced (from a person, a review of merged code, an agent or discovery) and may become an item. An open issue that intake has not yet placed on the roadmap is a candidate.
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
Re-ranking items, moving them between planned releases and the backlog, starting each release by filling it to size, and holding the current release to its admission rule and size. A person's ranking and placement stand; the admission rule, the cut and the size bind everyone.
_Avoid_: guard, governor, scope governor

**Closure**:
Closing a delivered item with a summary of what changed, and cutting a release, with its changelog, once every item in it is closed or descoped.
_Avoid_: completion, wrap-up

**Service**:
The long-running devops-cli deployment that runs the roadmap jobs when they are due, as found by webhook or by polling.
_Avoid_: runner, bot, daemon, worker

## Code review

**Finding**:
A reviewer's claim that something in the code is wrong, with where it is and the evidence for it.
_Avoid_: issue, alert, problem

**Verdict**:
The decision on a finding: verified (real), invalidated (a false positive) or mitigated (fixed).
_Avoid_: status, resolution

**Review session**:
One review run: what was reviewed, every finding it raised and their verdicts.
_Avoid_: review run, report

**Known false positive**:
A kind of finding reviewers keep raising wrongly, recorded once with how to recognize and disprove it.
_Avoid_: common hallucination, hallucination entry
