# Proposal: #5162 read the default branch at origin, not the working tree

## Why

Closes #5162. `devops infra onboard` read the working tree of the local checkout. On 2026-11-12 the first live run on dan-petty/homelab read a checkout on the merged branch `feat/node-crash-capture`, which is behind `origin/main` by homelab #19, #20 and #24. Row 9 reported 4 settings that turn host key checks off, but `origin/main` has host key checks on since homelab #24. The profile of a repository is read at its default branch, the trusted ref (#4627), and the plan of #5124 runs check mode on an exported commit. The later commands of tracker #5120 (`status`, `plan`, `apply`) read the same files, so the reader must give them one commit too.

## What Changes

- A shared reader, `src/devops_cli/infra/repo_tree.py`. `default_branch_tree(checkout)` fetches `origin`, takes the commit of `refs/remotes/origin/HEAD`, exports its tracked files with `git archive` into a new private folder, unpacks them with the `data` filter of `tarfile`, and removes the folder after the block. It records the default branch, its commit, and the branch and the commit of the checkout (`ReadCommit` in `models/infra.py`). It changes no file and no branch of the checkout.
- The fetch gets the credential of the GitHub session: `git -c credential.https://github.com.helper= -c 'credential.https://github.com.helper=!gh auth git-credential'`, with `GIT_TERMINAL_PROMPT=0` (`CONST_GIT_GITHUB_CREDENTIAL_CONFIG`). The process runner pins the session's `GH_TOKEN` on each git child, and `gh auth git-credential` reads it.
- `devops infra onboard` runs every read of the repo in the export and prints, under its title, the default branch and the commit that it read. When the checkout is at another commit, one more line names its branch (or a detached HEAD) and its commit. The dry run lists the four git commands before the Ansible commands.
- A failed git command, a checkout with no `refs/remotes/origin/HEAD` and an export that does not unpack raise `InfraReadError` (`INFRA_READ_FAILED`), with git's reason masked or the step `git -C <checkout> remote set-head origin --auto`.
- New setting default `DEFAULT_INFRA_GIT_TIMEOUT_SECONDS` (300 s) bounds each git command. The help of `devops infra onboard`, CONTEXT.md and the generated documents say that the command reads the default branch at origin.

## Capabilities

- `infra-onboard` (modified): the report reads the default branch at `origin`; the dry run lists its git commands.

## Impact

- `devops infra onboard` makes one request: the fetch of `origin`. It moves the remote-tracking branches of the checkout, as a `git fetch` of a person does. It needs a GitHub login that `gh auth token` gives.
- A checkout with no `refs/remotes/origin/HEAD` is refused with a step. `git clone` records it, and `git fetch` of git 2.48 or later records it when it is absent.
- `devops infra status`, `plan` and `apply` (#5123, #5124, #5125) use the same reader.

## Feasibility

- The live run of the fixed command on 2026-11-12 on dan-petty/homelab, with the checkout on `feat/node-crash-capture` at 6b5a7fa, read `origin/main` at f5961bd. Row 9 ("Host key checks are on") is `present`, and the report says that the checkout is on the branch `feat/node-crash-capture`. The checkout kept its branch and a clean `git status`. The output is in a comment of the pull request.
- `git rev-parse refs/remotes/origin/HEAD --abbrev-ref refs/remotes/origin/HEAD` in that checkout prints the commit and `origin/main` in one call; `git rev-parse HEAD --abbrev-ref HEAD` prints the commit and the branch of the checkout, and `HEAD` for a detached HEAD (git 2.55.0).
- The first live fetch through the process runner failed with `could not read Username`: the guard of `build_subprocess_env` does not pass the `GIT_CONFIG_*` keys of the devcontainer (`*KEY*` is a denied pattern), so git took the helper of VS Code from `/etc/gitconfig`, which needs keys that the guard also drops. With the two `-c` values, the same fetch passed. `_pin_github_token` in `core/process.py` gives each git child `GH_TOKEN`, and `gh auth git-credential` reads it (`gh auth setup-git` writes the same helper).
- `tarfile.extractall(filter="data")` (Python 3.14) refuses a link out of the destination and removes the group and other write bits, so Ansible reads the `ansible.cfg` of the export (it ignores the file in a folder that all users can write).

## Existing Tool Considered

git gives the fetch, the default branch, the commit and the export (`git fetch`, `git rev-parse`, `git archive`); `tarfile` of the standard library unpacks it with its `data` filter; `gh auth git-credential` gives the credential. `git worktree add --detach` (as `roadmap/clone_git.checkout_at` does) was not used: it writes into the `.git` folder of the checkout of a person. The reader is glue around these tools: about 0.4M tokens to build, 0.05M tokens a quarter to keep and fix, and 1.5 hours.
