# devops-cli

devops-cli automates DevOps work across the GitHub repositories it manages. This glossary holds the terms specific to that work.

## Release planning

**Roadmap**:
The current release, the planned releases and the backlog, taken together.
_Avoid_: plan, board

**Item**:
One unit of planned work on the roadmap, tracked as exactly one issue. Every open issue is an item except tracking issues.
_Avoid_: task, deliverable, card, ticket, work item

**Task file**:
The in-repo implementation record of one item, written in the pull request that delivers it.
_Avoid_: task, task item

**Priority**:
An item's rank: P0 (critical), P1 (high), P2 (medium) or P3 (low).
_Avoid_: severity, category, priority category

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
A started item with no commits, pull request activity or status change for the configured stall window. It is treated as not started again, so it can be descoped.
_Avoid_: stale, abandoned

**Not planned**:
An item closed without being delivered. It stays on record so the same idea is recognized as a duplicate if it surfaces again.
_Avoid_: rejected, won't fix, deferred

**Release**:
A numbered version that ships a fixed set of items.
_Avoid_: milestone, sprint

**Current release**:
The one release being worked toward now. Its scope is fixed when work on it starts; after that, only a critical fix can join it.
_Avoid_: active milestone, air-locked milestone

**Planned release**:
A later release whose scope is tentative and can be reshuffled freely until it becomes the current release.
_Avoid_: scheduled milestone, future milestone

**Backlog**:
The single prioritized pool of items not assigned to any release.
_Avoid_: icebox, triage queue

**Critical fix**:
A P0 item that fixes a defect, a security advisory or a regression. It is the only kind of item that can join the current release after it starts; a P0 feature waits for the next release instead.
_Avoid_: hotfix, P0 item

**Descope**:
To move an item that hasn't started out of the current release into the next planned release.
_Avoid_: rollover, defer

**Cut**:
Opening a release's pull request. From then on the release accepts no more items.
_Avoid_: freeze, air-lock

**Ship**:
A release ships when its pull request merges and it is published; the next release starts at that moment.
_Avoid_: publish, deliver

## Roadmap jobs

**Candidate**:
Something that surfaced (from a person, a review, an agent or discovery) and may become an item.
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
Re-ranking items, moving them between planned releases and the backlog, and holding the current release to its admission rule and size.
_Avoid_: guard, governor, scope governor

**Closure**:
Closing a delivered item with a summary of what changed, and writing a release's changelog when it is cut.
_Avoid_: completion, wrap-up
