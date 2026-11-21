# Proposal: #6655

## Why

Part B of #3702 applies the agent patch with git plumbing in two new git folders, and fetches through `OriginGit`. The owner asked for a plain issue-branch flow (#3702 comment 7065393209). Closes #6655.

## What Changes

- `publish_patch` makes a new repository, fetches the base at depth 1, applies each patch with `git apply --index`, commits as the bot, and pushes with `--force-with-lease`.
- The agent phase writes the patch with fixed format flags.
- `prepare` of fix-checks makes a plain clone in the run folder on the head branch (`phases/checkout.py`). The URL carry and `--source` go.

## Capabilities

- `roadmap-phases`: the plain clone, the patch format and the publish in a new repository.
- `roadmap-fix-checks`: the clone and the target of the push.

## Impact

fix-checks pushes the same one commit of the bot with a lease on the judged head. `devops roadmap step fix-checks` has no `--source`; no caller passes it.

## Feasibility

`git apply --index` refuses a path in `.git` and a write through a link, and `git push --force-with-lease=<ref>:<sha>` works with a lease that the new repository does not hold and with an empty lease (probes of the git audit, git 2.55). The end-to-end tests of fix-checks run on real git.

## Existing Tool Considered

Git porcelain, as `actions/checkout` uses it. Cost: about 900 changed lines.
