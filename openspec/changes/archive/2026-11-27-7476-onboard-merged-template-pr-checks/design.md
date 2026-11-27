# Design

## Decisions

- **Row 9 reads the check runs of the open template pull request only.**: The head of a merged pull request ran the workflows of that time. dan-petty/devtools#99 reported `Semantic PR title`, and after dan-petty/devtools#115 the title check reports `PR title / Semantic PR title` (issue body of #7476). An open pull request is the one that row 9 opened or that still waits, so its head shows the workflows that the next pull request runs.
- **A merged or closed template pull request gives no check to drop either.**: The first confirmed run already wrote the checks of that pull request into the live ruleset (D3). A live check that skipped on an old head can report now, and a drop from old evidence removes a check that protects the branch.
- **`_open_pull` serves both paths of `template_row`.**: `src/devops_cli/github/onboard/template_pr.py:def _open_pull` already lists the open pull requests of the head `ci/repository-template`, so the present path sends the same count of requests and `_last_template_pull` goes.

## Rejected alternatives

- **Keep the merged pull request and add only the names that the live ruleset already requires.**: The test `test_a_template_pull_request_that_is_not_open_gives_row_10_no_check[merged-skipped-live-check]` shows the second effect of old evidence: on the base commit row 10 sent `PUT /repos/example-org/app/rulesets/7` and dropped `K8s` from a skipped run of the old head.
- **Keep the drop list of a merged pull request and add no name from it.**: A drop of a live check from old evidence also changes the ruleset with no current run behind it, and the issue of #7476 asks that a later run keep the live checks.
- **Read the check runs of the head of the default branch.**: The archived design of #7318 rejected it: a job that calls a reusable workflow reports `<job> / <called job>` when it runs and `<job>` when it skips, so a name can be absent from the default branch head.
- **Compare the merge date of the pull request with the last change of `.github/workflows`.**: A workflow that a reusable workflow of another repository changes, such as the title workflow of infra, changes no file of the repository, so the date gives no proof.
