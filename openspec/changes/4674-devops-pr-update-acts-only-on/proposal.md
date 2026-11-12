# Proposal: #4674

## Why

`devops pr update --all` sends the GitHub update-branch request for each open pull request of the account that is not a draft. It does not check for a conflict or for a failed check (#4674). In the census week (2026-11-04 to 2026-11-11), update-branch merges of `main` with no conflict started 28 runs (about 1,208 runner-minutes), and 17 of them came in the groups that `--all` makes. GitHub cannot update a branch that has a conflict. `docs/SDLC.md` (No Catch-Up Updates) allows an update only for a conflict, or for a failed required check whose fix is on `main`. The owner decided on 2026-11-11 to keep the command only for that check case.

## What Changes

- Delete `--all`/`-a`, `--base`/`-B` and the loop over the open pull requests, with its planner, its listing arguments, its constant, its messages and its tests. Delete `sort_prs_oldest_first`, which has no other caller.
- `devops pr update <number>` reads the pull request. When GitHub reports a conflict (`merge_conflict` of `github/merge_readiness.py`), the command prints the local rebase steps, sends no other request and exits 1.
- With no conflict, the command reads the checks that the rules of the base branch require and the check runs of the head. It sends update-branch, locked to the head that it read, only when a required check failed. In the other cases it prints the reason, changes nothing and exits 0. A read that fails updates nothing and exits 1.
- The release pick and the command read the required checks with one function, `read_required_check_names` of `github/check_verdict.py`.
- The skill `devops-pr-ci` (three agent roots) gets the lines that start, rebase and push a branch with no catch-up push.
- `docs/SDLC.md` (No Catch-Up Updates) tells what the command does. The command documents are generated again.

The command, its options and its messages are observable, so the change has a spec delta.

## Capabilities

- New: `pr-update`.

## Impact

- `devops pr update --all` gives a usage error. Only the update of one pull request stays.
- The command makes no catch-up merge. This removes most of the about 25 merges of `main` per week that GitHub made for the command, and the CI runs that each merge started.
- The change fits one pull request.

## Feasibility

- GitHub documentation, "Keeping your pull request in sync with the base branch": update-branch cannot update a branch that has a merge conflict. The REST read of a pull request gives `mergeable` and `mergeable_state` (`dirty` for a conflict). The REST read `rules/branches/<branch>` gives the rule `required_status_checks`, which `release/merge_candidate.py` already reads for `main`.
- The source of the 13 pure-rebase topic runs of 2026-11-11 (CI audit). I read each run with `devops gh api repos/<repo>/actions/runs/<id>`. All 13 have the event `pull_request`, and the owner account is the actor and the triggering actor. Each head is a local commit whose committer is the git name of the workstation, not `GitHub`. update-branch makes a merge commit whose committer is `GitHub`, and the roadmap jobs commit with the login of their session as `user.name` (`roadmap/run.py`). Thus agent sessions on the workstation pushed all 13 after a local rebase. `devops pr update` and the cluster jobs did not push them.
- For each of the 13 runs, I ran `git merge-tree --write-tree --name-only <new base> <previous head>`. In 8 runs, the previous head had a conflict with the new base in an `openspec/specs/*/spec.md` file (an archive append). `git patch-id` ignores line numbers, so the fix of such a conflict keeps the patch-id. These 8 are the rebases that ADR 0014 asks for. The other 5 had no conflict: they pushed the same commits again after `main` moved by 1 or 2 commits. The rule "rebase right before each push", with a second push of the same commits, makes such a catch-up push. The new line of the skill `devops-pr-ci` forbids a push only to catch up.

## Existing Tool Considered

GitHub REST update-branch, `mergeable_state` and the branch rules read cover the decision, and `gh` sends the update. The change adds no tool. It builds only the decision, about 30 lines: about 150,000 tokens and 2 hours to build, and near zero to keep.

Internal code that the change deletes: `open_prs_argv`, `plan_update_all_prs`, `_fetch_open_prs`, `_process_candidate_pr_row`, `_update_all_prs`, `sort_prs_oldest_first`, `CONST_PR_UPDATE_AUTHOR`, the six messages and two help texts of the bulk path, and `_required_checks` of the release pick (it moves to `read_required_check_names`).
