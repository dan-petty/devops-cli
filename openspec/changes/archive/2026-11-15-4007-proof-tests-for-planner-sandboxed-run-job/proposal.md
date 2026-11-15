# Proposal: #4007

## Why

ADR 0018 records the isolation controls of the planner's sandboxed run Job: the read-only clone,
no credential and no service account token, and no egress. #4003 put the template and the
NetworkPolicy in git, but no test proves that the controls hold. A later edit could widen a mount
or add an egress rule and no check would fail. Closes #4007.

## What Changes

- Add `tests/roadmap/test_roadmap_run_job.py` with three offline tests over the Job that
  `build_job` renders from `cronjob-planner-run.yaml` and over the committed NetworkPolicy:
  a write outside the read-only copy fails, a credential read finds no file, and an outbound
  connection fails.
- Add the live test `test_the_run_job_holds_the_three_controls`, marked `k8s`, which runs a write,
  a credential read and a public connection in a real cluster Job pod.
- Declare the `k8s` marker in `pyproject.toml` and deselect its tests in a default run, as the
  `bwrap` marker does.

## Capabilities

None. The change edits tests and the test configuration only, so it sets `skip_specs: true`.

## Impact

Tests only. No `devops` command, message, manifest or image changes. The live test runs only with
`pytest -m k8s` on a host with a reachable cluster, and it skips without one.

## Feasibility

Premise checked on 2026-11-15 against `origin/main`: `PLANNER_TEMPLATE` and `build_job` are in
`src/devops_cli/k8s/cluster_job.py`, the CronJob and the NetworkPolicy are in
`k8s/devops/roadmap-service/`, and the three offline tests pass. The live test skips here because
no cluster is reachable.

## Existing Tool Considered

pytest, a dev dependency, reads the committed manifests and renders the Job. No new tool.
