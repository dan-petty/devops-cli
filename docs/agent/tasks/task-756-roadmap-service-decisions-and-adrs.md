# Task: Record the Roadmap Service Decisions and the Machine-Account and Polling ADRs (#756)

**Issue**: [#756](https://github.com/dan-petty/devops-cli/issues/756)
**Status**: Done
**Milestone**: v0.2.24
**Priority**: priority/p1-high
**Scope**: scope/docs

## Description
Records the outcome of the second roadmap design session: the glossary's resolved boundaries between the roadmap jobs, the service that runs them in the homelab, the decision to act as a machine account and the decision to treat polling as the source of change.

## Acceptance Criteria
- [x] `CONTEXT.md` defines Item, Candidate, Blocked, Dependency, Stalled, Cut, Current release, Critical fix, Value, Effort, Reprioritization, Closure and Service, each with the words to avoid.
- [x] `docs/adr/0002-roadmap-jobs-act-as-a-machine-account.md` and `docs/adr/0003-polling-is-how-the-roadmap-sees-changes.md` record each decision, the rejected options and its consequences.
- [x] `docs/ROADMAP.md` carries the revised #739, #740, #742 and #743 entries, lists #741, #752 and #753 under v0.2.26, and has backlog matrix rows for #754 and #755.

## Deliverables
- [x] `CONTEXT.md`
- [x] `docs/adr/0002-roadmap-jobs-act-as-a-machine-account.md`
- [x] `docs/adr/0003-polling-is-how-the-roadmap-sees-changes.md`
- [x] `docs/ROADMAP.md`
- [x] `CHANGELOG.md`
