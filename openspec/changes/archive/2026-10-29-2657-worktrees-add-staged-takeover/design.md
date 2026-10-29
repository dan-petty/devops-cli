# Design

## Context

See proposal.md for the motivation and the evidence.

- `add_worktree` in `src/devops_cli/git/worktree_add.py` refuses an issue when a local worktree holds it, then reads `git ls-remote --heads origin` and refuses when a branch of `origin` names the issue (#2337). Tests in `tests/test_repos_worktrees_add.py` use real repositories and a bare `origin` in `tmp_path`.
- `GitHubAppConfig.bot_login` gives `<slug>[bot]`. The Service and the cluster jobs commit as that identity (ADR 0015).
- `branch_form.py` holds the branch form. It reads only the issue of a branch today.

## Goals / Non-Goals

**Goals:**

- An agent can make the worktree of a branch that the App pushed, and continue its work.
- A branch that a person touched stays refused, with the author named.

**Non-Goals:**

- No check of the GitHub account behind a commit. See the first decision.
- No lock and no GitHub request. `add` stays on git.
- No take-over of a branch that already has a local worktree. The local holder check comes first and refuses it, as before.

## Decisions

**The author is the author name of the commit, compared with the bot login.** `git log --format=%an origin/main..origin/<branch>` lists one author name for each commit past the main branch. The rule needs every name to equal `GitHubAppConfig.bot_login`. The issue names this read. Rejected: the GitHub API field `author.login` of each commit. It needs one request, or a GraphQL query, for the branch, and `add` makes no GitHub request for its claim check (#2337). It also does not stop a forged name any better than git does for a person who can push to the branch.

**A branch with no commit past main is refused.** An empty branch shows no work by the App, and a person may have pushed it as a claim. Taking it over would make the "every commit" rule true for no commit. Rejected: a take-over with 0 commits.

**An unset slug refuses the branch.** `bot_login` is None without a slug, so no author can match. The refusal names `service.github_app.slug`, so the reader knows the cause. Rejected: a default login, which is a guess at private configuration.

**The branch of `origin` gives the type and the slug.** The branch form is read by one pattern with named groups in `branch_form.py` (`parse_branch`), and `issue_of_branch` uses it. Rejected: a second pattern in `worktree_add.py`, which could drift from the first.

**`--type` and `--slug` are optional, and checked after the read of `origin`.** The options cannot be checked before the read, because the staged branch decides what they must equal. The check of their form (a type of the list, a slug of the pattern) still runs first, so a bad value is a usage error before any git command. A missing option with no staged branch is a `GitOperationError` (exit 1) that names both options. A dry run reads nothing from `origin`, so it needs both options, and without one it is a usage error (exit 2). Rejected: keep both required. The agent that continues a staged item has the issue number and not the slug.

**The take-over fetches the branch with an explicit refspec.** `git fetch origin main +refs/heads/<branch>:refs/remotes/origin/<branch>` makes `origin/<branch>` exist even in a clone whose fetch refspec covers only `main`. Rejected: `git fetch origin <branch>`, which updates the remote-tracking ref only when the configured refspec covers it.

**The worktree uses `git worktree add --track -b <branch> <path> origin/<branch>`.** The upstream is the pushed branch, so a plain `git push` goes to the branch. A new branch keeps `--no-track`, because its base is `origin/main`. A local branch of the same name without a worktree makes git refuse `-b`, and the error of git is shown. Rejected: `-B`, which would reset that local branch and lose commits that are not pushed.

**Order of a real run:** check the form of the given values, read the local worktrees, read `origin`, then either create (no branch) or fetch, read the authors and add the worktree (a branch). Every refusal comes before the worktree is added, so a refused run leaves no worktree and no local branch.

**The dry run lists four commands.** `ls-remote`, `fetch origin main`, `log` and `worktree add --no-track`. The `log` and the `--track` form apply when `origin` holds a branch, and the notes of the plan say so. Rejected: a plan that reads `origin` to know which form applies, which breaks "a dry run makes no request".
