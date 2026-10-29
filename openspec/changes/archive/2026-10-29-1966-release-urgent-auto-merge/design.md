# Design

## Decision

One step in the `release-please` job of `release.yml`, after `Run release-please`, decides whether the pushed commit is an urgent fix and, if it is, turns on auto-merge of the release pull request with the release App token.

- **Trigger:** the pull request of the pushed commit has `release-now`, or an issue it closes has `priority/p0-critical`, or `type/security` with `priority/p1-high`. Intake sets the priority labels of an issue, and a person sets `release-now`.
- **Guard:** the step skips the run of a release merge (`releases_created`) and a run in which release-please returned no release pull request.
- **Values reach the script through `env:`**, never through `${{ }}` in `run:`.

## Rejected Alternatives

- **A merge loop that polls the checks and merges.** GitHub auto-merge does this, and rule 3 of AGENTS.md puts the tool first.
- **`GITHUB_TOKEN`.** GitHub's documentation says events that `GITHUB_TOKEN` causes start no workflow run, so the merge would start no `Release` run, and no release would be created.
- **A separate workflow on `pull_request: closed`.** It needs a second job with the App token, and it can run before release-please has put the fix into the release pull request. The same job runs after release-please has updated it.
- **Every `fix` title.** Each fix would release at once. The owner asked for labels and rules, and the labels say which fix is urgent.
- **Read `Closes #N` from the pull request body.** `closingIssuesReferences` is GitHub's own list of the issues that the pull request closes.
- **The label name `release/now`.** The guards `test_no_workflow_targets_a_release_branch_or_runs_release_tooling` and `test_no_agent_instruction_names_a_deleted_process` refuse `release/` so that the release-branch process cannot return. A guard exception would be an escape, so the label is `release-now`.
