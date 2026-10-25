# Proposal

## Why

Issue #2266: the repository squash-merges each pull request with its title as the subject and its body as the message, so the body stays in `git log`. The documents say only that the squash commit takes the title. The pull request template gives two Markdown headings, a rule and a `Change:` line that names the change folder before its archive. Of the last 60 merges on `main`, 49 messages hold headings, 32 report test runs and 11 say that a step is pending, which is true only during the review.

The owner also set on 2026-10-25 that a branch holds the latest `origin/main` when it is first pushed, and that a pull request that is open needs no rebase to catch up.

## What Changes

- `CONTRIBUTING.md` says that the squash commit takes the body as its message. A new rule says what the body holds (what the change does, and why, then `Closes #<issue>`, the `Change:` line and, when it applies, `Fail-to-pass: not applicable: <reason>`), and that test results, check status, steps for a person and the history of the issue go in a comment. A fix pull request cites its `fail-to-pass` check run in a comment.
- `.github/pull_request_template.md` has no heading and no rule, and its `Change:` line names the archived folder.
- `docs/SDLC.md`, Phase 1, step 5: before the first push, the branch is rebased onto `origin/main` if `main` moved. A pull request that is open needs no rebase to catch up.
- `tests/test_pr_cmd.py` checks that the template has no heading or rule line and that it names the archived folder.
- The change alters only documents and a test of a document, which a consumer of `devops` does not observe, so it has no spec delta and sets `skip_specs: true`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `CONTRIBUTING.md`, `docs/SDLC.md`, `.github/pull_request_template.md`.
- Tests: `tests/test_pr_cmd.py`.

## Feasibility

- `devops gh api repos/dan-petty/devops-cli` on 2026-10-25 gave `allow_squash_merge: true`, `allow_merge_commit: false`, `allow_rebase_merge: false`, `squash_merge_commit_title: PR_TITLE` and `squash_merge_commit_message: PR_BODY`. Thus the body is the message of the commit on `main`.
- `git log -1 990e4d1f --format=%B` (#2226) holds the body with its `## Summary`, `## Tests` and `## Item` headings, a test count and a "Pending a person" line.
- `devops pr create` passes `--body` to `gh pr create`, so the template is used only when a person opens a pull request on the web. The fail-to-pass workflow reads only the `Fail-to-pass: not applicable: <reason>` line of the body, and `devops pr check-readiness` reads the closing issue from GitHub, not from a heading. A body with no heading passes both.

## Existing Tool Considered

GitHub's squash merge settings (`PR_TITLE`, `PR_BODY`) and the Git trailer form for the closing lines. The change adds no code and deletes none.
