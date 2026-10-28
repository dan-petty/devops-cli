# Design

## The verdict is data

`assess_merge_readiness` returns a frozen `MergeReadiness`. A blocker is a string, as the command printed it. An advisory is a `(level, text)` pair, a warning or an information line, and never changes an exit code. The checks still running are a fact of their own, so #2443 can tell "pending" from "blocked" without parsing a string. The review threads that block are kept for a caller that lists them. The command alone prints and exits.

Each option (`allow_draft`, `allow_blocked_state`, `allow_replied_threads`, `allow_pending_checks`) turns its blocker into an advisory, as the command did.

## Where the code lives

The verdict reads GitHub, so it lives in `github/`. The item rules state the Item definition of CONTEXT.md and ADR 0016 and read nothing, so they are pure predicates in `roadmap/`. The closing-issue model (`ClosingIssue`) lives with the rules, because they judge it. The GraphQL query that reads it lives with the verdict.

## How a test reaches GitHub

Readiness reads GitHub two ways: its checks and the changed files through the GitHub session, and the commit statuses, review threads, change directory and closing issues through `gh`. The verdict takes both (`runner`, `session`), as `GitHubRoadmapStore` does.

The tests give it neither and fake the two edges instead, so `run_gh`, its pacing and the session's paging run for real. `github_api` refuses `gh`, because a real `gh` would send the pinned token to GitHub. The new fixture `github_api_and_gh` serves the session over `GitHubApiFake` and sends `gh` to `process_fake`, where no `gh` starts.

`list_pr_review_threads` resolves its default runner when it runs, not when the module loads, so the existing thread tests that patch `pr_threads.run_gh` keep working until #1324 moves them onto the fakes.

## Rejected alternatives

- **A scripted runner and `RunnerSession` in each verdict test.** The roadmap store tests script `gh` this way. `docs/TESTING.md` asks for one fake per edge, shared, and `process_fake` is the fake of the `gh` edge. A scripted runner per test file would be a second double of that edge.
- **The verdict reads the pull request itself.** `check-readiness` reads it first, to report a merged or closed pull request and to resolve replied threads before it judges. A second read in the verdict would cost one more request. The verdict takes the payload, and #2443 decides one read for every command.
- **The verdict prints the thread table.** That is rendering, and the MCP tool and #2443's monitor do not want a table. The verdict keeps the threads, and the command prints them.
- **Keep the order of today's output exactly.** The thread table printed between the replied-thread line and the later warnings. Exact order would put rendering items in the verdict. The command prints the advisories, then the table, then the blockers. Every line stays the same.
