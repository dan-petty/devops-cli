# Proposal: #6618

## Why

Tier 1 of the step `fix-conflict` runs `devops docs generate` and `uv lock` in the checkout of a bot pull request. Both run code of that checkout: the entry point of the project and its build hooks. The code of the step ran tier 1 and pushed on any host, also without `--confirm`, and fetched and pushed through the remote `origin` of the clone. The implement and fix-checks Jobs run such code only in a runner Job, and reach `origin` only through `OriginGit`.

Tier 1 could not run before this change. The clone of the step is shallow and holds only the default branch, so `git fetch origin <head>` wrote no remote-tracking ref, and `git checkout <head>` failed. The docs and lockfile path passed `dict(os.environ, GIT_EDITOR="true")` to `git rebase --continue`, and the process runner refuses that override. A fix of the checkout makes tier 1 run, so it comes with the gate. Closes #6618.

## What Changes

- `devops roadmap step fix-conflict` rebases, runs tier 1 and pushes only with `--confirm`. With `--confirm` the command calls `require_runner`, `deny_environment_reads` and `adopt_orphans` before the step, as fix-checks does. Without `--confirm` the step returns the new result `planned` with the conflicted files. It runs no code of the checkout, pushes nothing and writes no record.
- The step reads the URL of `origin` right after its clone. Each fetch and push of the step runs through `OriginGit` at that URL. The push has a lease on the head that the step judged.
- Each local git call of the step runs with `core.hooksPath=/dev/null`, the new constant `CONST_GIT_HOOKS_OFF_CONFIG`, which `CONST_GIT_TOKEN_CALL_CONFIG` also uses.
- The step checks out the head branch only before the rebase, as `git checkout -B <head> origin/<head>`, from the remote-tracking ref that the fetch of `OriginGit` writes. So the checkout works in the shallow clone.
- `git rebase --continue` takes its editor from `-c core.editor=true` (the new constant `CONST_GIT_NO_EDITOR_CONFIG`), and no git call of the step passes an environment variable.
- A rebase that fails with no conflicted file stops the round. Before a push, the step checks that HEAD is the head branch, holds the tip of the default branch and differs from it, and holds each change of the pull request. It never pushes the tip of the default branch.
- Right after the clone, the step writes the identity of the bot into the clone (`commit_author`, which was `_commit_author` of `ensure_checkout`).
- The step deepens its shallow clone through `OriginGit` (`fetch(deepen=...)`) until it holds the merge base, and fails with a clear reason when the history holds none. `git merge-tree` that fails for another cause than a conflict raises.
- The plan names what a confirmed round does: a stop for a release path, a path that tier 1 does not settle, or `tier1_mode` other than `on`.
- `OriginGit` writes the remote-tracking refs of the clone with the hooks of the clone off, and a fetch that makes the history whole removes the `shallow` file of the clone.
- The setting `roadmap.fix_conflict.tier2_mode` goes: no code reads it, and no tier 2 exists. The configuration models of `roadmap` ignore an unknown key, so a configuration that still names it loads.
- The git calls of tier 1 put `--` before each path.
- The help of the command and its generated reference say this.

The command, its option and its result change, so the change carries a spec delta.

## Capabilities

- `roadmap-fix-conflict`: MODIFIED requirement 'Tier 1 resolves deterministic conflicts with no model call'; ADDED requirements 'Tier 1 runs only in a runner Job', 'The step reaches origin only at the URL that it read after its clone', 'The step continues a rebase with no environment override', 'A round pushes only a result that holds the default branch and the pull request', 'The clone of the step commits as the bot', 'The step fetches the history to the merge base' and 'The plan says what a confirmed round does'.
- `roadmap-implement-runner`: ADDED requirements 'A network git call writes the refs of the clone with its hooks off' and 'A fetch can deepen a shallow clone'.

## Impact

On a workstation the step gives its plan. A runner Job runs tier 1 and the push. The process runner does not change. The change fits one pull request.

## Feasibility

- On main, `src/devops_cli/roadmap/steps/fix_conflict.py` stops at `git checkout <head>` (git 2.55: a clone with `--depth=50` fetches only `+refs/heads/main:refs/remotes/origin/main`). The step module of main, run on its own clone path, raised `GitOperationError` at the checkout and ran no `uv` process.
- With a full clone (`source`), main ran `uv run devops docs generate` on the archive path and pushed with `git push --force-with-lease origin`, with or without `--confirm`. The docs and lockfile path raised `SecurityError` at `git rebase --continue`.
- The new command and step tests fail on main and pass after the change. The step tests use local bare repositories, real git through the process runner, and the token of the test floor.
- `OriginGit` and `origin_url` (`src/devops_cli/roadmap/implement/git_isolation.py`) already serve the implement Job, fix-checks and review.

## Existing Tool Considered

The change reuses `require_runner`, `deny_environment_reads`, `adopt_orphans`, `OriginGit` and `origin_url`. It adds two constants and the option `deepen` of `OriginGit.fetch`, which `git fetch --deepen` serves. It deletes the fetch and the push of the step through the named remote, and the reason "Tier 2 is in plan mode without --confirm", which no path reaches now.
