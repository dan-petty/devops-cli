# Design

## Decisions

- **One reader for every `devops infra` command.** `infra/repo_tree.py: default_branch_tree(checkout)` is a context manager that gives the root of the export and a `ReadCommit`. `onboard` reads in it now; `status`, `plan` and `apply` read in it when they come. `plan` will take another ref (`--ref`) through the same module.
- **Fetch, then read `refs/remotes/origin/HEAD`.** The commit of the default branch at `origin` is the trusted ref of the profile (#4627). The reader does not ask GitHub for the default branch: `git clone` records it, and `git fetch` of git 2.48 or later records it when it is absent. A checkout with none gets a step (`git remote set-head origin --auto`), not a guess.
- **`git archive` into a private folder.** The export holds the tracked files of one commit and nothing of the working tree: no uncommitted change, no ignored file. It writes nothing into the checkout. The folder comes from `tempfile.mkdtemp` (mode 0700), and the `data` filter of `tarfile` unpacks it. The block removes it.
- **The credential of the GitHub session.** The `-c` values name `gh auth git-credential` for github.com and clear the helpers of the config files first. git gets the session's `GH_TOKEN` from the process runner. No other key of the environment of the person reaches git.
- **Two lines in the text report.** The first names the default branch and the commit, always. The second shows only when the checkout is at another commit. `OnboardReport.read` holds the same facts for a program.

## Rejected alternatives

- **`isolate_env=False` for the fetch** (as the release pushes of #1124 did). The person's whole environment, credentials included, would reach git and every program that its config starts. ARCHITECTURE.md asks for the keys that a child needs only.
- **`git worktree add --detach`.** It writes the metadata of a worktree into the `.git` folder of the checkout of a person, and another agent can work in that checkout at the same time.
- **The tarball of the GitHub API.** It needs no checkout, but every later command needs the checkout for `plan --ref` of a pull request head, and it puts a second path to the same files beside git.
- **Read the working tree and warn when it is not on the default branch.** A warning does not fix a wrong row 9. A plan and an apply must read one commit.
