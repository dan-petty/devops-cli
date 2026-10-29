# Proposal

## Why

Issue #2657, a part of #2653: the roadmap `stage` job pushes a branch `<type>/<issue>-<slug>` with the App's commits for an item. `devops repos worktrees add` refuses an issue when `origin` holds a branch for it (#2337). So no agent can make the worktree of a staged item, and the staged change is lost to them. A stopped implement run of the same job leaves the App's code commits on a pushed branch, and the same refusal hides those commits too.

## What Changes

- `worktrees add <issue>` reads the pushed branch of the issue. When every commit of the branch past `origin/main` has the App's bot login as its author, the command takes the branch over. The login is `service.github_app.slug` with the `[bot]` suffix (`GitHubAppConfig.bot_login`). The worktree is made on that branch, with `origin/<branch>` as its upstream. The output says that the command took over a staged branch, and gives the number of commits.
- A pushed branch with a commit by any other author is refused as today, and the error names that author. A branch with no commit past `origin/main`, and any pushed branch when `service.github_app.slug` is not set, is refused too.
- A stopped implement run leaves the App's code commits on its branch. The same rule takes them over. The command adds no second rule.
- When the pushed branch exists, `--type` and `--slug` come from it, so both options are optional. A `--type` or `--slug` that differs from the branch is an error that names the branch. When `origin` holds no branch for the issue, both options are still required, and the new branch has no upstream as before.
- `--dry-run` lists four git commands: the `ls-remote` read, the fetch, the `log` read of the authors, and the create. It makes no request. It needs `--type` and `--slug`, because it cannot read the branch of `origin`.
- The JSON report has the new status `took over` and the field `commits`.
- CONTRIBUTING.md (the worktree row of "Naming" and the paragraph on starting work), `docs/ROUTINE_TASKS.md` and `docs/SDLC.md` Phase 1 say that `worktrees add` takes over a staged branch.
- This change fits one pull request. It changes the capability `repos-worktrees-add`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-worktrees-add`: a pushed branch with only the App's commits is taken over and not refused; `--type` and `--slug` come from that branch; the dry run lists the author read.

## Impact

- `src/devops_cli/git/branch_form.py`, `src/devops_cli/git/worktree_add.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- Tests: `tests/test_repos_worktrees_add.py`, `tests/test_branch_form.py`.
- Documents: `CONTRIBUTING.md`, `docs/ROUTINE_TASKS.md`, `docs/SDLC.md`, and the generated `README.md`, `docs/CLI_REFERENCE.md` and `docs/commands/repos.md`.
- The change deletes no code.

## Feasibility

- Command output (git 2.55.0): in a scratch repository, a branch `feat/9-x` with two commits by the author `devops-roadmap[bot]` was pushed to a bare `origin`. After `git fetch origin main +refs/heads/feat/9-x:refs/remotes/origin/feat/9-x`, the command `git log --format=%an origin/main..origin/feat/9-x` printed `devops-roadmap[bot]` twice. Then `git worktree add --track -b feat/9-x <path> origin/feat/9-x` created the worktree, and `git rev-parse --abbrev-ref @{u}` printed `origin/feat/9-x`.
- Source: `GitHubAppConfig.bot_login` in `src/devops_cli/config/settings.py` returns `<slug>[bot]`, or None without a slug. The change reads it and builds no second login rule.
- Limit: the author name of a commit is text that its writer chooses, so this rule is a guard against a mistake and not against a person who forges an author. The issue chose this rule. A check of the GitHub login of each commit would need one request for each commit and breaks the rule that `add` reads git only (#2337).
- The stage job (#2654) is not merged. The rule depends only on the author of the commits, so it holds for the commits of any App run.

## Existing Tool Considered

- git covers all of it: `ls-remote --heads` finds the branch, `log --format=%an` lists the authors, and `worktree add --track -b` makes the worktree on the branch. The login comes from the existing setting. Nothing new is built, and no code is deleted.
