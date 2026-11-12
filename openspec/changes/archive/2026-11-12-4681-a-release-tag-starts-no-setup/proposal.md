# Proposal: #4681

## Why

Each release tag starts the Copilot Setup Steps workflow. The `push` trigger of `.github/workflows/copilot-setup-steps.yml` has only a `paths` filter, and GitHub does not read a path filter for a tag push. From 2026-11-04 to 2026-11-11, 124 of the 127 push runs of the workflow came from release tags. These runs test nothing that changed. Closes #4681.

## What Changes

- The `push` trigger of `.github/workflows/copilot-setup-steps.yml` gets `branches: ["**"]`. A tag push then matches no filter and starts no run. A branch push that changes the workflow file still starts a run, and the `pull_request` and `workflow_dispatch` triggers do not change.
- A new contract test in `tests/invariants/test_workflow_contracts.py` refuses each workflow whose `push` trigger has a `paths` or `paths-ignore` filter and no branch or tag filter. The problem cannot come back in another workflow.
- The change alters a CI workflow and a test only. A consumer of `devops` sees no change, so the change has no spec delta.
- The change fits one pull request.

## Capabilities

None. The change edits one workflow and one test.

## Impact

- About 120 fewer workflow runs each week, one for each release tag.
- The Copilot cloud agent does not change: GitHub runs the `copilot-setup-steps` job from the default branch before the agent starts, and that does not use the `push` trigger.
- No setting, dependency or document changes.

## Feasibility

- The workflow syntax reference of GitHub Actions (docs.github.com, `on.push.paths`) says: "Path filters are not evaluated for pushes of tags." The `on.push.branches` section says that with only `branches` or `branches-ignore`, "the workflow won't run for events affecting the undefined Git ref". A `branches` filter with no `tags` filter thus starts the workflow on no tag.
- The Actions API (`actions/workflows/copilot-setup-steps.yml/runs?event=push&created=2026-11-04..2026-11-11`) gives 127 runs: 124 with a `v<version>` tag as `head_branch` and 3 with a branch.
- Of the 5 workflows of `origin/main` at 310981773 with a `push` trigger, 2 have a path filter: `pages.yml` also has `branches`, and `copilot-setup-steps.yml` has no branch or tag filter. The new test fails on the base with `['copilot-setup-steps.yml']`.

## Existing Tool Considered

The `on.push.branches` filter of GitHub Actions covers the need, and actionlint checks the syntax. The guard is a short pytest case in the existing workflow contract tests.
