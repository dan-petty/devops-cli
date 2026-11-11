# Proposal: #4540

## Why

Intake is due only on a `REOPENED` change or on a fresh candidate that the last round left. The change feed reads the repository issue events, and these events report no opened issue. So when the scoped update of a new issue is lost (no replica during a rollout, or a lost queue entry), the new issue waits for the intake interval of 29 minutes. Closes #4540.

## What Changes

- `RoadmapStore.newest_issue_number()` gives the number of the newest issue that is no pull request. The GitHub store reads it from the first page of `issues?state=all&sort=created&direction=desc&per_page=10`, which the session sends with the ETag of its last answer.
- The intake record keeps `newest`: the newest issue when the last intake round started.
- The intake due rule reads the newest issue when nothing else makes intake due, and makes intake due when that issue is newer than the record's `newest`.
- A scoped update keeps `newest` as it was, so a lost delivery of an older issue still makes intake due.
- `docs/roadmap/intake.md` tells when the Service runs intake, and the help of `devops roadmap run` names the new issue.

## Capabilities

- `roadmap-scoped-updates`: adds the requirement "A new issue makes intake due at the next poll".

## Impact

- One more GitHub request for each poll of each repository on the triage lane, when the record has a newest issue and nothing else makes intake due: 7 repositories every 300 s is about 84 an hour. Most of them are 304 answers, which GitHub does not count against the primary rate limit.
- One more request at the start of each intake round, which the session also sends with its ETag.
- After the deploy, the record has no `newest` until the next intake round writes it. Until then, the rule makes no read and intake keeps the old rule.
- An issue that 10 or more newer pull requests push off the first page waits for the 29-minute interval, as today.

## Feasibility

- The issue events do not report an opened issue. `devops gh api 'repos/{owner}/{repo}/issues/4540/events?per_page=100' --jq '[.[].event] | unique'` gave `["labeled","parent_issue_added","unlabeled"]` for the issue that opened on 2026-11-11. The repository feed `issues/events?per_page=100` gave no `opened` kind either. So `ChangeKind.OPENED` cannot come from this feed, and the change uses the issue listing.
- The issue listing sorts by creation time: `devops gh api 'repos/{owner}/{repo}/issues?state=all&sort=created&direction=desc&per_page=30'` gave the newest 30 entries, 24 of them issues and 6 pull requests, newest first.
- `GitHubSession.paginate` sends each page that links a next page with `If-None-Match`, and gives back the kept items on a 304 (`src/devops_cli/github/session.py`).

## Existing Tool Considered

The GitHub REST issue listing with `sort=created` and the session's conditional reads cover the need. No new tool or library. Cost: about 50,000 tokens and 2 hours to build, about 2,000 tokens a month to keep, about 5,000 tokens to fix.
