# Proposal: #6618

## Why

Tier 1 of the step `fix-conflict` runs `devops docs generate` and `uv lock` in the checkout of a bot pull request. Both run code of that checkout. The step could not reach tier 1: its clone (`--depth=50`) held only the default branch, so `git checkout <head>` failed. The docs and lockfile path also failed, because the process runner refuses `GIT_EDITOR`. A fix of the clone makes tier 1 run, so it comes with the runner gate. Closes #6618.

## What Changes

- `devops roadmap step fix-conflict` rebases, runs tier 1 and pushes only with `--confirm`, which runs only in a runner Job (`require_runner`, `deny_environment_reads`, `adopt_orphans`, as fix-checks). Without `--confirm` the step returns the new result `planned` and runs no code of the checkout.
- The step clones into a new folder of the run with `ensure_checkout`, as fix-checks does, switches to the head branch, and pushes through `OriginGit` to the URL that it read before tier 1, with a lease on the judged head.
- Tier 1 settles each stop of the rebase. It takes the default branch for generated documents and `uv.lock` (`git checkout --ours`, or `git rm` for a file that the default branch deleted) and continues with `-c core.editor=true`. It drops only the archive commit of the item, which moves the change folder into the archive (`git rebase --skip`), and archives the change again after the rebase.
- A rebase that fails with no conflicted file, or a git call that fails, stops the round, and the step records the stop. The step pushes only a result with a commit past the default branch. Only `openspec validate --specs --strict` runs before the push.
- The authors come from `person_authors`. The conflicted paths come from `git merge-tree --name-only`. The plan and the round ask one release check.
- When a round in the implement job fails, the branch gets back its tip from before the rebase, not the tip of main.
- The unused setting `roadmap.fix_conflict.tier2_mode` goes.

## Capabilities

- `roadmap-fix-conflict`: RENAMED 'Strict validation and scoped checks run before push' to 'Strict validation runs before push', and MODIFIED it; MODIFIED 'Tier 1 resolves deterministic conflicts with no model call', 'A conflict on a release path stops with class conflict' and 'The runner job calls fix-conflict on rebase conflicts'; ADDED 'Tier 1 runs only in a runner Job', 'The step works in a clone of its run and pushes through OriginGit' and 'The plan says what a confirmed round does'.

## Impact

On a workstation the step gives its plan. A runner Job runs tier 1 and the push. The process runner and `OriginGit` do not change. The change fits one pull request.

## Feasibility

- On main, the step module ran on its own clone path raised `GitOperationError` at `git checkout <head>` and ran no `uv` process (git 2.55).
- The new tests use local bare repositories and real git through the process runner. They cover an archive commit that is not the tip, an archive commit that holds code, a spec commit that is no archive commit, a generated document that main deleted, a git call that fails, a renamed file, a merge of main into the branch, a `uv.lock` conflict whose plan and round agree, and the tip of the implement branch after a failed round.

## Existing Tool Considered

The change uses plain git (`ensure_checkout`, `git switch`, `git rebase --skip`, `git merge-tree --name-only`) and the project tools `person_authors`, `OriginGit`, `require_runner` and `process_hardening`. It deletes the depth-50 clone, the search for the archive commit by its subject, the parse of the merge-tree messages and the author check of the step.
