# Design

## Decisions

### One no-CI rule in the merge-readiness verdict

`_judge_checks` decides that no check can start, so `devops pr check-readiness`, `devops pr
ready` and `devops pr monitor` share one verdict. The verdict sets `no_ci`, adds an INFO advisory
and adds no `CHECKS_PENDING` blocker. `devops pr ready` reads `no_ci` instead of the branch-wide
workflow count.

### Read the workflow triggers at the head commit

`GitHubClient.pull_request_workflow_at` lists `.github/workflows` at the head commit, reads each
YAML file and parses its `on` key. A workflow that lists `pull_request` or `pull_request_target`
can start a check on the pull request. A missing folder means no CI. A folder that holds only
`push` or `workflow_dispatch` workflows also means no CI.

YAML 1.1 reads a bare `on` key as the boolean `True`, so the parser reads both keys.

### Fail closed on an unread workflow

A read error, or a workflow file that is not valid YAML, keeps the pending check. An unread
workflow is no proof that no check can start, so `devops pr ready` waits (exit 8) and
`devops pr monitor` waits until its timeout rather than report a pull request ready.

### A conflict stops the monitor before the pending check

Once the no-CI rule removes the pending stand-in, the monitor's settled result names the merge
conflict at once. It no longer sleeps for a check that no workflow will start.

### Remove `count_workflows`

The branch-wide count reads no trigger and no head commit, so it answered the wrong question. No
caller remains after this change.

## Rejected alternatives

- **Keep `count_workflows`:** it counts workflows on any branch and ignores triggers, so it
  reports CI for a workflow that cannot run on a pull request.
- **Fix each command separately:** three copies drift, and #5142 already left `pr monitor` and
  `check-readiness` behind.
- **Read the workflow file names only:** a workflow with only `push` or `workflow_dispatch`
  triggers cannot start a check on the pull request.
- **Treat an unread workflow as no CI:** that reports a pull request ready on no evidence.
