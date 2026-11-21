# Design

## Decisions

- **Plain git** (owner decision of 2026-11-21, #3702 comment 7065393209). `publish` works as `actions/checkout` does: `git init`, a fetch of the base at depth 1, `git switch --detach`, then `git apply --index` and `git commit` as the bot for each patch, and `git push --force-with-lease=refs/heads/<branch>:<lease>`. An empty lease makes a new branch, and the push fails when the branch exists. git itself refuses a path in `.git`, a path outside the tree and a write through a link; `publish` refuses the link, gitlink, `.gitmodules` and workflow changes from `git diff --cached --raw`.
- **More than one patch.** `publish_patch` takes a list of patches and writes one commit for each, so the implement Job (#3702) can keep its archive as its own commit. fix-checks gives one patch.
- **The new tree for the claim check.** `before_push` gets the new tree (`NewTree`), which reads names and files from the git objects. A new tree that the lease holds already gets no push.
- **A fixed patch format.** `git diff --binary --full-index --no-color --no-ext-diff --no-textconv --src-prefix=a/ --dst-prefix=b/`, so no diff setting of the clone or of the home folder changes the patch.
- **A plain clone in `prepare`.** `clone_branch` clones the repository on GitHub into the run folder, which is new to the run, switches to the head branch after the author check, and gives the base and the lease. The clone holds no setting that the check of the steps refuses. The URL of `origin` is no longer carried from `prepare` to `publish`: `publish` pushes to the repository on GitHub. `--source` goes, because each run makes its own clone.
- **Until #3700, git reads no global or system configuration in `prepare` and `publish`** (`git_call`): `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1` and the credential helper from `-c` values. `publish` ends the leftover processes once first, because the home folder is shared in `--phase all`.
- **fix-checks keeps its base and lease rules**: both are the judged head. Its rebase is #6639.

## Rejected alternatives

- Git plumbing on a second git folder that shares the objects of the first: porcelain in one new repository does the same with less code.
- A patch from a new bare git folder on the objects of the clone: the fixed format flags keep the settings of the clone out of the patch with plain git.
