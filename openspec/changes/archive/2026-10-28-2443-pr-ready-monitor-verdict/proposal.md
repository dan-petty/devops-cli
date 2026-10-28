# Proposal

## Why

Issue #2443, part 2 of #998: `devops pr ready` and `devops pr monitor` (and its alias `pr wait`) judge a pull request with their own code, apart from the merge-readiness verdict that #2442 made for `devops pr check-readiness`.

- `github/pr_monitor.py` reads the pull request with `fetch_pr_details`, and `commands/pr.py` has a second `_fetch_pr_details`.
- The mergeable state is judged twice, with different rules. The monitor blocks a branch that is `behind` its base, and `check-readiness` does not.
- Unresolved review threads are judged twice.
- `pr ready` reads its checks through a third path, `check_verdict.fetch_pr_check_verdicts`. When it cannot read the pull request, it skips the check read and marks the pull request ready.
- `pr monitor` stops at the first failing check while other checks still run, so a blocker that comes later shows only on a second run.

## What Changes

- The verdict keeps each blocker with its kind (`BlockerKind`): closed, conflict, mergeability unknown, branch protection, draft, failing checks, unread checks, running checks, review threads, unread review threads, grounding. It also keeps the check read it made. `MergeReadiness.blockers` stays the tuple of blocker texts, so `check-readiness` prints the same lines.
- One function reads a pull request: `fetch_pr_details` in `github/pr_monitor.py`. The `_fetch_pr_details` of `commands/pr.py` is deleted. The commands that show a pull request read it through `fetch_pr_details` too.
- `pr monitor` judges each poll through the verdict, beside its own review gate (requested changes, Copilot review, approval with `--require-reviews`), which `check-readiness` does not have. While a check runs or a Copilot review is active, it waits, whatever other blockers it sees. When the checks settle, it reports every blocker at once and exits 1 when a check failed or could not be read, 2 for any other blocker, and 3 on its timeout. Its own mergeable, draft, thread and check rules are deleted.
- `pr ready` reads the verdict. It exits 1 when a check failed or could not be read and 8 while a check runs, as before. It prints the other blockers as warnings and still marks the pull request ready. When it cannot read the pull request, it stops with exit 1, unless `--force` is given.
- A branch that is `behind` its base blocks in no command.
- The behavior of `pr monitor` and `pr ready` changes, so the change carries a spec delta: the new capability `pr-merge-readiness`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `pr-merge-readiness`: how `devops pr ready` and `devops pr monitor` judge a pull request from the one merge-readiness verdict and map it to their exit codes.

## Impact

- `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/github/pr_monitor.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/errors.py`, `src/devops_cli/lang/en/help.py`.
- `tests/test_merge_readiness.py`, `tests/commands/test_pr.py`, `tests/test_github_pr_monitor.py`, `tests/test_pr_cmd.py`.
- `docs/commands/pr.md` and `docs/CLI_REFERENCE.md`, which `devops docs generate --sync-readme` rewrites.

## Feasibility

- On `origin/main` 08d70ca6, `rg -n 'def _?fetch_pr_details' src` finds two functions: `github/pr_monitor.py` and `commands/pr.py`. The monitor's mergeable rules are `_resolve_merge_failure_reason`, `_check_early_pr_failures` and `_evaluate_pr_settled_readiness`; `_check_early_pr_failures` returns on the first failing check whatever still runs.
- `pr ready` calls `fetch_pr_check_verdicts` only when the pull request payload has a head commit. `_fetch_pr_details` returns `{}` on any read failure, so a failed read skips the check verification.
- The ruleset of `main` (`gh api repos/dan-petty/devops-cli/rules/branches/main`, 2026-10-28) has `strict_required_status_checks_policy: false` and `required_approving_review_count: 0`. GitHub merges a branch that is behind its base, so `behind` is no blocker. Where a ruleset requires an up-to-date branch, GitHub reports `mergeable_state: blocked`, which the verdict blocks.
- The verdict already reads every check of the head commit through `read_commit_checks`, with each item's name, workflow, state, link and bucket. The monitor can show its check table from that read with no second read.
- Copilot's review and the reviewers' verdicts are read only by the monitor (`_fetch_raw_reviews`, `_detect_copilot_status`). `check-readiness` does not judge reviews, so the review gate stays with the monitor and is added to the verdict's blockers.
- The criterion "No test patches `devops_cli.commands.pr.run_gh`" is read as #998 wrote it: the readiness tests (`pr ready`, `pr monitor`, `pr check-readiness`). The tests of `pr create`, `list`, `view`, `edit`, `diff`, `close`, `update` and `hardening-report` are not readiness tests and stay.

## Existing Tool Considered

`gh pr checks --watch` waits for the checks of a pull request, but it does not judge review threads, Copilot reviews, the draft state or the item rules. The monitor keeps its loop and reads the one verdict. The change deletes the monitor's own mergeable, draft, thread and check rules, `PRCheckRun`, the second pull request read in `commands/pr.py`, and `pr ready`'s own check-verdict rendering.
