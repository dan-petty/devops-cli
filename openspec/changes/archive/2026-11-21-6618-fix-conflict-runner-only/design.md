# Design

## Decisions

- The gate is `--confirm` in the command, as in fix-checks. The command calls `require_runner`, then `deny_environment_reads` and `adopt_orphans`, and then the step. The step rebases and runs tier 1 only with `confirm`, so the tests of the step do not change the test process.
- Without `confirm` the step stops after the check of the caps. It checks out no head branch and rebases nothing, so no file of the head is in the working tree.
- No path of tier 1 settles a conflict with git alone: the archive path and the docs path run `devops docs generate`, and the lockfile path runs `uv lock`. So the step has no part to keep on a workstation, and it gives its plan.
- The checkout uses `git checkout -B <head> origin/<head>`: `OriginGit.fetch` writes `refs/remotes/origin/<head>` with an explicit refspec, which the shallow clone with one branch lacks.
- `git rebase --continue` gets `-c core.editor=true` as an argument. The process runner refuses `GIT_EDITOR` from a caller, and a caller environment would also skip its filter of the variables of the process.
- The push is `OriginGit.push` with a lease on `status.head_sha`. In a runner Job, `OriginGit` checks the git settings of the clone before each fetch and push, as for the implement Job.

- The check before the push compares paths, not patches: tier 1 takes the default branch for a generated file, so the patch of such a commit changes. The check leaves out the paths that the default branch also changed and the paths that tier 1 generates.
- The clone deepens twice as far each time from 50 commits, so a fork that is n commits behind needs about log2(n / 50) fetches, and a fetch that adds no commit ends the loop.

## Rejected alternatives

- A full clone in place of `--depth=50`: each round would fetch the whole history, about 2,300 commits of main, also when the fork is recent.
- `git fetch --unshallow` at the first missing merge base: the same cost as a full clone.
- A patch-id or `git range-diff` check before the push: a commit whose generated file tier 1 replaced has another patch id, so the check would refuse each settled round.

- A change of the process runner for every git child: other callers reach a named remote, so that change needs an item of its own.
- An explicit URL in the git folder of the clone: git still reads the configuration of the clone for that URL. `OriginGit` reads no configuration of the clone.
