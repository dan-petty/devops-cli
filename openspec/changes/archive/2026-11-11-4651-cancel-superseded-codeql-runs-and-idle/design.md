# Design

## Decisions
- CodeQL group: `codeql-${{ github.event_name == 'pull_request' && github.ref || github.run_id }}` with `cancel-in-progress: true`. A pull request has one group for each ref, so a newer push cancels the old head. Each push to `main` and each scheduled run is alone in its group, so nothing cancels it.
- CodeQL timeout: `timeout-minutes: 15` on the `analyze` job. The steps have no timeout of their own, so the job limit is the inner limit of the run.
- Fail-to-Pass: one expression names a body edit: `github.event.action == 'edited' && !github.event.changes.title && !github.event.changes.base`. The job condition starts with its negation, and the concurrency group adds `github.run_id` for it and `head` for every other event. So a body edit run is skipped and never cancels the replay of the head.
- The base is part of the expression because the replay reads `github.base_ref`. An edit of the base changes the replay.
- Cleanup: remove the `pull_request` trigger, the `CLOSING_PR_NUMBER` variable and the block that used it. Keep the daily schedule, which also deletes untagged digests older than 1 day, and `workflow_dispatch`.

## Rejected alternatives
- CodeQL group for each ref with `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`, as the issue proposed. On `main`, a newer push cancels a pending run in the same group even when `cancel-in-progress` is false (GitHub workflow syntax reference), so some commits of `main` would get no analysis.
- `queue: max` for the `main` group. The reference says that `queue: max` with `cancel-in-progress: true` is a validation error, so the pull request group would need another workflow. A group of its own run is simpler.
- Only a job condition on the Fail-to-Pass job, as the issue proposed. The body edit run would enter the group of the replay and cancel it. `_without_replaced_cancellations` drops that cancelled run, so the head would show only a skipped check.
- Job-level concurrency on the Fail-to-Pass job. The workflow syntax reference does not say whether a job that its `if` skips enters the group, so the result is not known.
- Remove `edited` from the trigger types. A change of the title to a fix title must start the replay, and a change away from a fix title must skip it.
- Delete `cleanup-devcontainer.yml`. ADR 0012 and #1858 delete it together with the image workflow. The schedule still prunes untagged and orphaned digests until then.
