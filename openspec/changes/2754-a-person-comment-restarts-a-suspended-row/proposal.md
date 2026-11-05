# Proposal

## Why

Issue #2754: a comment by a person on an item does not start a suspended row again. A row that failed `DEFAULT_SERVICE_MAX_FAILED_ROUNDS` rounds in a row does not run until its input changes. The input of a round (`_round_input` in `src/devops_cli/roadmap/run.py`) is a digest of the issue events since the oldest last success and, for a trigger that is not a poll, the time of the round. A comment is neither. The Service takes only the `issues` webhook event, so an `issue_comment` delivery gets `no_subscriber`. A person who answers on an item of a suspended row must wait for an unrelated issue event.

[ADR 0009](../../../docs/adr/0009-one-webhook-router-delivers-each-event-to-the-consumers-subscribed-to-it.md) left `issue_comment` out on purpose, because #1361 measured 940 webhook triggers in one hour. This change must not bring that load back, and it must stay under `service.github_requests_per_hour`.

## What Changes

- The store protocol gets `comments_since(since)`. It gives the comments of the whole repository, on issues and pull requests, newest first, one page at a time as the caller asks. `GitHubRoadmapStore` reads `GET repos/<repo>/issues/comments?sort=created&direction=desc&since=<UTC time>`. `InMemoryRoadmapStore` gives its comments in the same order.
- `trust.py` gets `is_person_comment(comment, actor)`. A comment is a person's when its author has write access (`author_association` OWNER, MEMBER or COLLABORATOR), its login does not end in `[bot]`, and it is not the account that the process acts as.
- `FailureLedger` gets `holds_failure(repo, job)`: whether the job failed a round that no success has cleared.
- A round that has a row which may run and holds a failed round reads the comment listing once. It starts at the oldest last success of those rows (with no limit when one of them never succeeded) and stops at the first comment of a person. Each of those rows gets the time of that comment, unless the comment is older than the last success of the row.
- `_round_input` adds that time to the digest of the row only when the row has one. The digest of a row with no such comment is the digest of before, so the ledger file keeps its format and a record written by the running version stays valid.
- A new person comment changes the digest, so the suspended row runs again and counts its failed rounds from one. A comment of a bot, of the account of the process, of a person with no write access, or one made before the last success changes nothing. A poll with no new comment changes nothing.
- A round with no failed row reads no comment. A dry run reads no comment. A failed read ends the round with its error and counts as no failed round of a row, as a failed read of the issue events does.
- The log line that suspends a row says that a comment of a person is also new input. `k8s/README.md` (step 11 of the Roadmap service setup) says the same, with the measured cost.
- The change carries a spec delta on `roadmap-service-limits`, because the Service behavior and the log line are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-limits`: a comment of a person starts a suspended job again, at a cost of one listing for each lane in a round.

## Impact

- Code: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/trust.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_suspended_row_comment.py`, `tests/roadmap/test_roadmap_github_store.py`
- Documents: `k8s/README.md`
- The change deletes no code.

## Feasibility

- **The premise holds.** `FailureLedger.suspended` compares the digest of the round with the digest of the last failure. `_round_input` holds the issue events and the round time only (read in `src/devops_cli/roadmap/run.py`). `CONST_ROADMAP_WEBHOOK_EVENTS` has no `issue_comment`. So a comment cannot change the digest today.
- **The design of the issue body does not fit the request budget.** The refine block of the issue reads the open Items updated since the last success of the row, and then lists the comments of each of them. Real system, 2026-11-05: `uv run devops gh api 'repos/dan-petty/devops-cli/issues?state=open&since=2026-11-04T18:24:45Z&sort=updated&direction=desc&per_page=100'` returned a full page of 100 open issues and pull requests changed in 24 hours. The Service polls every `DEFAULT_SERVICE_POLL_INTERVAL_SECONDS` (151 s), which is 24 polls an hour, and `DEFAULT_SERVICE_GITHUB_REQUESTS_PER_HOUR` is 500. One failing row with 100 updated Items would send 100 listings in each poll, which is 2,400 requests an hour. The test scenario of the refine block (three rows with ten Items each) is 33 requests in a poll and 792 in an hour. Both are over the budget. ADR 0016 already measured 775 requests for one read of the comments of every Item.
- **One repository listing fits.** `uv run devops gh api 'repos/dan-petty/devops-cli/issues/comments?since=2026-11-04T18:24:45Z&sort=created&direction=desc&per_page=100'` returned a full first page of 100 comments made in 3 hours 28 minutes. Each comment has `author_association`, `user.login` and `created_at`. Of the 100 comments, 49 are by a person with write access on an issue, 40 by `devops-cli-service[bot]` and 2 by `dan-petty-release[bot]` (association CONTRIBUTOR each), and the first comment of a person is at position 6. A read that stops at the first comment of a person is one request. At 24 polls an hour and three lanes, the worst case with a failed row in each lane is 72 requests an hour, 14% of the budget.
- **The GitHub documents agree.** The page `https://docs.github.com/en/rest/issues/comments`, "List issue comments for a repository", says `sort` is `created` or `updated`, `direction` is `asc` or `desc`, `per_page` is at most 100, and `since` filters on the time a comment was last updated. So `since` can only bound the read, and the order is by creation. The row digest uses the creation time of the comment, so an edit of an old comment starts nothing.
- **The session stops when the caller stops.** `GitHubSession.paginate` in `src/devops_cli/github/session.py` is a generator: "A consumer that stops early sends no further request". The test `test_a_consumer_that_stops_after_the_first_item_sends_one_request` in `tests/github/test_github_session.py` pins it.
- **The author is already read.** `IssueComment.author_login` and `author_association` exist (`src/devops_cli/roadmap/store.py`, requirement "Item and IssueRecord carry the author login" of `roadmap-author-trust`, test `test_a_comment_carries_its_authors_login_and_association`). The "Comment author is read" requirement of the refine block needs no new code and no new requirement.
- **The repository is public.** `src/devops_cli/roadmap/trust.py` says so. A comment of any account would let a stranger restart a failed row at will, so only a person with write access counts, as for the `implement: retry` comment.
- **The ledger needs no new field.** `FailureLedger.failed` starts the count at 1 when the input differs from the input of the last failure (`rounds + 1 if failed_on == current or rounds < limit else 1`). The existing test `test_a_job_reports_its_suspension_until_new_input_or_a_success_ends_it` shows it. So `service-failures.json` keeps its format.
- **The failing test first.** `uv run devops ci test tests/roadmap/test_roadmap_suspended_row_comment.py` must fail on the base, before the code of this change exists.

## Existing Tool Considered

The GitHub REST listing `GET /repos/{owner}/{repo}/issues/comments` with `sort`, `direction` and `since`, read through the paginating session that the store already uses, covers the data and the early stop. The alternatives check of the issue named PyGithub (`Issue.get_comments(since=...)`, LGPL-3.0, last activity 2026-10-13, maintained). It lists the comments of one issue, so it brings the per-Item read that the measure above rejects, and a second GitHub client beside the session that holds the conditional requests and the hourly budget gate. It is not used. The `issue_comment` webhook event is rejected by ADR 0009. The change builds the filter (`is_person_comment`) and the digest field. Cost: about 15,000 tokens to build, about 2,000 tokens for each fix to keep it, and one working day elapsed.
