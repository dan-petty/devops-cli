# Design

## Context

#2420 hands the qualifying findings of a review session to `devops roadmap intake`. Intake files every candidate (#2223), so the review must leave out a finding that an issue already carries. The owner decided the rules on 2026-10-28 (comment on #883): a fingerprint v2 match is the same finding; an issue closed as not planned keeps the finding out; an issue closed as completed does not.

## Decisions

### The marker is an HTML comment with a fixed phrase and the fingerprint

`<!-- devops-review-finding: fingerprint_v2=<64 lowercase hex> -->`. GitHub does not show an HTML comment. The phrase `devops-review-finding` is what the search matches, and the parser reads only a 64-character hex fingerprint after it. `finding_marker` refuses any other value with a `ValidationError`, because a marker that the parser cannot read would let the same finding be filed again.

### One search for the phrase, and the bodies are parsed locally

`read_filed_findings` sends `"devops-review-finding" in:body is:issue repo:<repo>` and parses the fingerprints from the bodies it gets. One request returns up to 100 marked issues, so the cost grows with the number of filed findings, not with the number of findings a session has. The parser is the authority: search only gives the set of bodies to parse.

### The client reads search pages by number and fails closed

GitHub marks a search answer `incomplete_results` when the search timed out, and returns at most 1,000 results. `search_issue_bodies` raises `GitHubUnreadError` for an incomplete page and for a `total_count` past `DEFAULT_GH_SEARCH_MAX_RESULTS`. A short answer would let the review file findings that an issue already carries.

### Which issues settle a finding

- Open: settles. An issue tracks it.
- Closed as not planned: settles. A person rejected it; a suppression in `.devops/review.toml` is the fix.
- Closed as a duplicate: settles. The owner decision does not name this reason. Another issue tracks the finding, so a new issue would be one more duplicate.
- Closed as completed: does not settle. The defect came back.

One settling issue is enough: a finding carried by a completed issue and by an open one stays out.

### A dry run makes no request

`read_filed_findings(repo, dry_run=True)` touches neither the GitHub session nor `gh auth token`, and returns an empty lookup with the planned search (`planned_session_read`). With no issue known, `unfiled` keeps every finding, which is what the real run gives when no issue carries one.

## Rejected alternatives

- **One search for each fingerprint.** A review of release/v0.2.25 admitted 41 tool findings in one run (#1137 baselines). 41 search requests are more than the 30 that the `search` quota allows in a minute.
- **A list of the issues with a label.** The issue listing (`GET /repos/{repo}/issues?labels=…&state=all`) spends the `core` quota and has no index lag. But intake would have to set a new label on each filed finding, and a person who removes a taxonomy label would make the review file the finding again. Listing `source/agent` instead reads every issue an agent filed, open and closed, to find the few that carry a marker. The marker in the body is the one record that the search reads.
- **`GitHubSession.paginate(..., iterable_key="items")`.** It follows the `Link` pages and yields the items only, so it drops `incomplete_results` and `total_count`, and an incomplete answer would read as complete.

## Risks

- **The search index lags.** GitHub updates the search index after a write. A second hand-off soon after the first can miss an issue that the first one filed, and file the same finding again. Intake's duplicate check then names the possible original for a person. #2420 sends one hand-off for each session, and a person runs it, so the window is small.
- **The 1,000-result cap.** Past 1,000 marked issues, the lookup fails and says why. A different read is needed then, for example a search that is narrowed by the date of the session.
