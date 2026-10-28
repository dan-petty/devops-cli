# Design

## The verdict keeps the kind of each blocker

`MergeReadiness.blocking` holds each blocker as a `Blocker(kind, text)`. `BlockerKind` names what blocks: `CLOSED`, `CONFLICT`, `MERGEABILITY`, `BRANCH_PROTECTION`, `DRAFT`, `CHECKS_FAILING`, `CHECKS_UNREAD`, `CHECKS_PENDING`, `THREADS`, `THREADS_UNREAD` and `GROUNDING`. `MergeReadiness.blockers` is the tuple of their texts, so `check-readiness` prints the same lines as before. `MergeReadiness.checks` is the `CheckVerdictSummary` that the verdict read, `None` when the payload names no head commit. Each command maps the kinds to its own exit codes.

## One pull request read

`fetch_pr_details(owner, repo_name, number, *, runner)` in `github/pr_monitor.py` is the one read. It raises `GitHubOperationError` when GitHub cannot answer. `check-readiness`, `pr ready` and the monitor stop on that error and name it. `pr view`, `pr checks` and `pr update` show what they can without the payload, as before, through one small adapter in `commands/pr.py` that gives them an empty payload on that error.

## `pr monitor`

Each poll reads the pull request once, judges it through the verdict, and reads the reviews and Copilot's timeline for the monitor's review gate:

- Copilot's review state could not be read: a blocker.
- Copilot requested or recommended changes, and a thread is still open: a blocker.
- A reviewer's latest review requests changes: a blocker.
- With `--require-reviews` (the default), no approval of the head commit: a blocker.

The monitor waits while the verdict names a running check or a Copilot review is active, whatever other blockers it sees. With `--require-reviews`, it also waits out `--settle-timeout`, so a Copilot review that starts late is seen. Then it reports every blocker, the verdict's and the review gate's, in one result:

| Settled result | Exit |
| :--- | :--- |
| No blocker | 0 |
| A check failed or could not be read | 1 |
| Any other blocker | 2 |
| The timeout passed first | 3 |

A merged pull request is ready, and nothing more is read. The command prints each blocker. A draft blocker is a warning with the hint to run `devops pr ready`, a thread blocker adds the thread table and the reply hint, and a check failure adds the log hint.

## `pr ready`

"Ready for review" tells reviewers that the work is done and its checks pass (AGENTS.md rule 6: mark it ready only after the checks pass). The merge itself stays gated by `check-readiness`, the required checks and a person. So `pr ready` blocks only on the checks: exit 1 when a check failed or could not be read, 8 while one runs, as before. It reads the full verdict and prints each other blocker (conflicts, open threads, the item rules such as a missing `priority/*` label) as a warning, so the author sees what still blocks the merge. It does not block on them. It reads the verdict with `allow_draft`, because the pull request is a draft until this command runs.

`--force` skips the verdict, as it skipped the check read before.

## `behind`

No command blocks a branch that is behind its base. The ruleset of `main` does not require an up-to-date branch (`strict_required_status_checks_policy: false`), so GitHub merges it. A repository whose ruleset requires an up-to-date branch reports `mergeable_state: blocked`, and the verdict blocks that.

## Rejected alternatives

- **Typed blockers replace the blocker texts.** `MergeReadiness.blockers` is read by `check-readiness` and by 20 assertions in `tests/test_merge_readiness.py`. A derived tuple of texts keeps them, and the kinds are one more field.
- **The review gate moves into the verdict.** `check-readiness` does not read reviews or Copilot's timeline. Moving them would add three reads and new blockers to it, a change that no item asks for. The monitor is the one command that waits for reviews.
- **`pr ready` blocks on every blocker of the verdict.** A draft with a missing `priority/*` label could then not be marked ready until intake labels its issue, and an open review thread would keep a pull request out of review, the step that resolves it. Agents may not set a priority label themselves (AGENTS.md).
- **`pr monitor` returns on the first blocker it sees.** This is the behavior #998 reported: a failing check returned while other required checks still ran, and the later blocker showed only on a second run.
- **A separate parameter for each fact on `MergeReadiness`** (failing check names, unread reason, draft flag). Each new fact would need its own field. The kind of a blocker and the check read give every command what it maps.
