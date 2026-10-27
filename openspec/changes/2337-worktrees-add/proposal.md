# Proposal

## Why

Issue #2337: several agents work on this repository at the same time, each in its own git worktree, and nothing creates a worktree in a standard way or tells an agent that another agent already works on an issue. On this host, 107 of 125 worktrees sit under a root that an agent tool chose, 12 under `.data/agent/worktrees/`, and the branch and directory names follow no rule. The branch form `<type>/<issue>-<slug>` is checked only at commit time. Two agents can start the same issue, and the second finds out at the pull request.

## What Changes

- `devops repos worktrees add <issue> --type <type> --slug <slug>` creates the worktree `w-<issue>` under the agent worktrees directory of the data directory (`.data/agent/worktrees/`). The branch is `<type>/<issue>-<slug>`. It starts at a freshly fetched `origin/main` and has no upstream, so a push needs `git push -u origin HEAD`.
- The command refuses an issue that is held. A worktree holds an issue when its branch has the form `<type>/<issue>-<slug>` for that issue, or when its directory is the standard path. A branch of `origin` with that form holds it too. The error names the holder: the path of the worktree or the name of the remote branch. A local branch without a worktree holds nothing.
- `--type` is one of the types of `release-please-config.json`, and `--slug` is lowercase letters, digits and hyphens. Both are required. A value that breaks the branch form is refused before any git command changes anything.
- `--dry-run` makes no request to `origin`. It reads the local worktrees, prints the `git ls-remote`, `git fetch` and `git worktree add` commands that the run would make, and creates nothing.
- `devops repos worktrees status` shows the issue number of each worktree, taken from its branch, as a column of the table and the field `issue` of the JSON.
- A test fails when the branch form of the code and the form that the `branch-name` pre-commit hook and `release-please-config.json` hold disagree.
- This change fits one pull request. It adds the capability `repos-worktrees-add`.

## Capabilities

### New Capabilities

- `repos-worktrees-add`: how `devops repos worktrees add` creates the worktree of an issue in one place and one branch form, and how it refuses an issue that a worktree or a pushed branch holds, and how `worktrees status` shows the issue of each worktree.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/git/worktree_add.py` (new), `src/devops_cli/git/worktree_inventory.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`.
- Tests: `tests/test_repos_worktrees_add.py` and a branch-form invariant test.
- Documents: `CONTRIBUTING.md` (the worktree row and the branch rule), and the generated `docs/CLI_REFERENCE.md`, `docs/commands/` and `README.md`.

## Feasibility

- Command output: `git ls-remote --heads origin` lists the 2 heads of this repository (git 2.55.0). It needs one network call and no GitHub API. `git worktree add --no-track -b <branch> <path> origin/main` creates a branch with no upstream: `git rev-parse --abbrev-ref @{u}` answers `fatal: no upstream configured`.
- The issue text lists a third source of a claim, an open pull request that closes the issue. GitHub's REST API has no closing-reference field for a pull request. The GraphQL field `Issue.closedByPullRequestsReferences` exists, but its answer for #2336 includes the open release pull request #2329, which would hold every issue that the release notes name. A same-repository pull request always has a pushed head branch, and the remote-branch check sees that branch. So the change reads worktrees and remote branches, uses git alone, and makes no GitHub request. This is smaller than the issue text on purpose.
- The change makes no lock. `devops repos worktrees prune` already keeps a worktree with no merged pull request at its tip (`repos-worktrees-prune`), and a lock would keep a merged worktree from ever being pruned.

## Existing Tool Considered

- `git worktree add` creates the worktree and is the only command that changes the repository. The claim check reads `git worktree list` and `git ls-remote`.
- `gh issue develop` links a branch to an issue and does not refuse a second branch. It needs the GitHub API, and AGENTS.md rule 7 sends GitHub requests through `devops gh`.
- No open tool refuses a second worktree for an issue, so the change builds the claim check. The cost is one module of about 150 lines and its tests, which stay in this one pull request. The change deletes no internal code.
