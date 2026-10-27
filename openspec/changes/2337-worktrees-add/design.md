# Design

## Context

See proposal.md for the motivation and the evidence.

- `devops repos worktrees` has `status` and `prune`. `inventory_worktrees` in `src/devops_cli/git/worktree_inventory.py` reads `git worktree list --porcelain -z` and enriches each entry with its branch, its commits ahead of main and its dirty count. Both commands take `--repo-dir`.
- The branch form `<type>/<issue>-<slug>` is held in three places today: the `branch-name` hook of `.pre-commit-config.yaml` (a regular expression), the types of `release-please-config.json`, and the table of CONTRIBUTING.md section 5.
- All worktrees of a repository share one data directory, and `resolve_data_path` resolves a relative data path under the main worktree. CONTRIBUTING.md puts agent worktrees "under `.data/agent/`".
- A dry run makes no external request and lists the requests the real run would make (`PlannedRequest`, `render_request_plan`). `prune` also uses the modes preview, `--dry-run` and `--confirm`.
- Tests build real repositories in `tmp_path` with the `git` fixture and call the command with the `cli` fixture. Git is a real program in tests, so a bare repository in `tmp_path` can serve as `origin`.

## Goals / Non-Goals

**Goals:**

- One command creates the worktree of an issue in one place and in the branch form that the hook accepts.
- The command refuses an issue that a worktree or a pushed branch holds, and says who holds it.
- The branch form lives in one place in the code, and a test fails when the hook or the release types disagree with it.

**Non-Goals:**

- No claim from an open pull request. See the decision below.
- No lock on the worktree, no board status change and no comment on the issue. A claim is a branch, and the board belongs to the roadmap commands.
- No check that the issue exists or is open. That needs the GitHub API, and `add` stays on git alone.
- No removal of worktrees. `prune` and #2338 own that.

## Decisions

**The claim comes from worktrees and remote branches only.** The issue lists a third source, an open pull request that closes the issue. GitHub's REST API has no closing-reference field. The GraphQL field `Issue.closedByPullRequestsReferences` answers for #2336 with three pull requests, one of them the open release pull request #2329, which would hold every issue that its notes name. A pull request of this repository always has a pushed head branch, and the remote-branch check sees it. Alternatives rejected: the GraphQL field (false claim from the release pull request, and GraphQL is the scarcer GitHub quota), and a REST list of open pull requests filtered by head branch (the same result as the remote-branch check at the cost of one more request).

**`origin` is read with `git ls-remote --heads origin`.** The repository has 2 heads, so the list is short and one call suffices. A pattern in the command would need git's glob rules for slashes, so the code lists all heads and keeps those that match the branch form for the issue. Alternative rejected: `GET /repos/{repo}/branches`, which needs the GitHub API and a repository name.

**One module holds the branch form.** `CONST_BRANCH_TYPES` and `CONST_BRANCH_SLUG_PATTERN` are in `config/constants.py`. The module `git/worktree_add.py` builds the whole-branch pattern from them and reads the issue of a branch with it. `worktree_inventory` uses the same reader for `status`. An invariant test checks that the types equal the types of `release-please-config.json` and that the `branch-name` hook pattern holds the same expression. Alternative rejected: read `release-please-config.json` at run time. The command also runs in checkouts of other repositories, which have no such file.

**The match is exact on the issue number.** The reader takes the digits between the first `/` and the next `-` and compares them as integers, so `feat/23370-x` is not issue 2337. The standard directory `w-<issue>` counts as a holder even when its branch differs, because `git worktree add` would fail on it.

**The base is `origin/main` after `git fetch origin main`, and the branch has no upstream.** `git worktree add --no-track -b <branch> <path> origin/main` makes the branch. Without `--no-track`, git sets `origin/main` as the upstream of the new branch, and a plain `git push` would then aim at `main`. Task 3.2 shows `@{u}` is unset. The fetch comes after the claim check, so a refused run changes nothing in the repository.

**Order of a real run:** check the branch form, read the local worktrees, read `origin`, fetch, create. Each step before the create can refuse, and only the last two change the repository. A failed git command raises `GitOperationError` with the message of git, as `prune` does.

**`--type` and `--slug` are required.** A default slug would need the title of the issue, which is a GitHub read, and a default type would hide a choice that the pull request title repeats. Alternative rejected: derive both from the issue title. The agent that starts an issue knows both.

**The dry run reads the local worktrees and nothing else.** Reading `git worktree list` is a local read, so a dry run still refuses an issue that a local worktree holds, and returns the same report type as the real run. The three commands that touch `origin` or the repository are listed as planned requests with their exact argument lists.

**`status` gets the field `issue`.** `WorktreeEntry` gains `issue: int | None`, read from the branch by the same reader. The table gets a column `Issue`. The JSON schema changes by one field. No other code in `src` reads `WorktreeEntry`.

## Risks / Trade-offs

- [A worktree whose branch has not yet taken the form, such as a fresh tool-made `level-quartz`, holds nothing] → The `branch-name` hook refuses the first commit on such a branch, so the branch takes the form before any work exists. The window is short and the claim comes with the branch.
- [Two agents run `add` for one issue within the same second] → Each reads `origin` before the other pushes, and both create a worktree. The second `git push` of the same branch name is refused; with a different slug it is not. The check narrows the window to the time between create and push, and does not close it. A lock on the remote would need a service, which the issue does not ask for.
- [`git ls-remote` fails with no network] → The command refuses with the message of git and creates nothing. `--dry-run` shows the command and needs no network.
- [A local branch with no worktree is ignored] → That branch is stale work, often a branch that `prune` left after a merge, and treating it as a claim would block an issue for good.
