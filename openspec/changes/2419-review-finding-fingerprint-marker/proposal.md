# Proposal

## Why

Issue #2419, part 2 of #883. Since #2223 (owner decision 2026-10-25), intake files every candidate and only names a possible duplicate. When a review hands its findings on merged code to intake (#2420), each run would therefore file the same finding again as a new issue. The owner decided on 2026-10-28 (comment on #883) that the review itself leaves out a finding that an issue already carries. The match is on the finding's fingerprint v2 (#1141). That is the same finding, not a model verdict, so it agrees with #2223.

## What Changes

- An issue that a review finding becomes carries the marker `<!-- devops-review-finding: fingerprint_v2=<hex> -->` in its body. `finding_marker` writes it, and `carried_fingerprints` reads every marker of a body. The marker is an HTML comment, so GitHub does not show it.
- `GitHubClient.search_issue_bodies` reads every issue of a repository, open or closed, whose body holds a phrase, through GitHub's issue search and the GitHub session. It reads the pages by number and refuses an answer that GitHub marks incomplete or that has more results than search returns, so a short answer never reads as a complete one.
- `read_filed_findings` makes one search for the marker's phrase and returns the issues that carry each fingerprint. With `dry_run`, it makes no request and returns the search that a real run sends.
- `FiledFindings.unfiled` leaves out each finding that an issue settles: an open issue, an issue closed as not planned, or an issue closed as a duplicate. A finding whose only issues were closed as completed stays, because the defect came back.
- No command calls the lookup yet. `devops review intake` (#2420) calls it before its hand-off, and writes the marker into each candidate body.
- The change carries a spec delta: the new capability `review-filed-findings`. It is the contract that #2420 builds on, and its marker is a format that the issues on GitHub keep.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `review-filed-findings`: the marker that an issue filed from a review finding carries, and which findings the review leaves out because an issue already carries them.

## Impact

- `src/devops_cli/github/client.py`: `search_issue_bodies` and its answer models.
- `src/devops_cli/review/filed_findings.py`: new.
- `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`.
- `tests/test_github_client.py`, `tests/test_review_filed_findings.py`.

## Feasibility

Checked on 2026-10-28 with read-only requests through `devops gh api` against `dan-petty/devops-cli`:

- **Search finds text inside an HTML comment.** Refine writes `<!-- checked-at: sha=<commit> -->` into the issues it refines, and that text is only in the comment. `"checked-at: sha" in:body is:issue repo:dan-petty/devops-cli is:closed` returned 150 issues, and each one holds the comment. The phrase `"devops-roadmap-refine:start"`, which is also only in a comment, returned 335.
- **Search matches a long hex token exactly.** The 40-character commit `bb46660c…0db` from such a comment returned 72 issues. The same token with its last character removed returned 0.
- **Each search item carries what the filter needs.** The items have `number`, `state`, `state_reason` (`completed`, `not_planned`, `duplicate`) and the full `body`. The page has `total_count` and `incomplete_results`.
- **Request cost.** One search request returns up to 100 issues. The answer reports `X-Ratelimit-Resource: search` with a limit of 30 requests a minute. That quota is separate from the 5,000-an-hour `core` quota and from GraphQL. A lookup costs one search request for each 100 issues that carry a marker. GitHub returns at most 1,000 results for one search, so the lookup refuses a search with more results than that.
- `fingerprint_v2` is the stable identity of an admitted finding (`src/devops_cli/review/fingerprint.py`). A session saves it in each tool finding's `fingerprint` field (`src/devops_cli/ai/review/pipeline.py`).

## Existing Tool Considered

GitHub's issue search finds the issues, and the GitHub session (gidgethub, ADR 0006) sends the request, paces it and charges its quota. The change builds no client and no index. It adds one typed call to `GitHubClient` and one module of about 100 lines for the marker and the filter. The change deletes no internal code: nothing else reads which findings an issue carries.
