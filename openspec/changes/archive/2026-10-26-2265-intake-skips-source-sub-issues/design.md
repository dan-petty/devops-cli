# Design

## Context

See proposal.md - Why.
`_Planner._decide` builds the set `apart` of numbers that stay out of a candidate's shortlist: the candidate itself and the issue its source links. A sub-issue of the source is a sibling part, and the parts of one split are planned to be different changes.

## Goals / Non-Goals

**Goals:**
- Leave the sub-issues of the source issue out of the comparison of a new candidate.
- Read the parent of an issue from the listing that intake already reads.

**Non-Goals:**
- Change how a candidate with no source, or a source that has no sub-issues, is compared.
- Exclude the sub-issues of an issue that is not the source.
- Read sub-issues that are not linked yet. A part that is filed and not yet linked is still compared, as before.

## Decisions

### Decision 1: Read `parent_issue_url` from the issue listing
- *Rationale*: The listing already carries the field, as `sub_issues_summary` already carries the sub-issue count. Intake sends no new request.
- *Alternatives considered*: Read `GET repos/{repo}/issues/{n}/sub_issues` for the source. Rejected: it needs one more request for each source, and the in-memory and GitHub stores would each need a second read path. Read the sub-issue links from the source's body. Rejected: a body is text that an author writes, and it may be out of date.

### Decision 2: Keep only a parent in the same repository
- *Rationale*: A sub-issue can have a parent in another repository, and its number means a different issue there. The payload's `repository_url` is the prefix of the same repository's issue URL, so the check needs no parse of the repository name and no case rule.
- *Alternatives considered*: Compare `parent_issue_url` with the repository name the store was opened with. Rejected: the name may differ in letter case from the name GitHub returns.

### Decision 3: Extend `apart` with the children of the source
- *Rationale*: The candidate, its source and the sub-issues of the source all leave the same shortlist for the same reason. One set keeps one rule.
- *Alternatives considered*: Mark the siblings as not compared in `_compared`. Rejected: that function has no candidate, and the exclusion depends on the candidate's source.

## Risks / Trade-offs

- [A sibling that is filed but not yet linked is still compared] -> The agent links each part right after it files it, so the next part sees it linked. A part whose link fails keeps today's behavior: a flag, and no part is dropped.
