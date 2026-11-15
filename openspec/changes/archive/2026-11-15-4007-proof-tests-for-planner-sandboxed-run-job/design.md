# Design: #4007

## Context

`build_job` copies the suspended CronJob's pod spec and changes only the args, the name, the
labels and some environment values. The pod spec in
`k8s/devops/roadmap-service/cronjob-planner-run.yaml` is therefore the isolation boundary that
ADR 0018 records, and `networkpolicy-planner-run.yaml` is the egress boundary.

## Decisions

- The offline tests render the Job with `build_job` and read the pod spec and the committed
  NetworkPolicy. They assert the values, not presence: the read-only mounts, the two writable
  `emptyDir` volumes, `automountServiceAccountToken: false`, no Secret volume and no `valueFrom`,
  and a policy with `Egress` and no egress rule.
- The live test adds the `k8s` marker and a `live("kubectl")` marker, replaces the container
  command with a shell probe, creates the Job in namespace `devops`, waits for completion and
  reads its log. It deletes the Job in a `finally` block and skips when no cluster is reachable.
- `pytest_collection_modifyitems` drops the `k8s` tests unless `-m k8s` selects them, as it does
  for `bwrap`, so a default run and the gate keep their time.

## Risks

- The live test writes to the shared `devops` namespace. The Job name is fixed and deleted after
  the run, and `concurrencyPolicy` does not apply to a Job made by hand. A stale Job with the
  same name makes `apply` replace it, which is the wanted result of a rerun.
- The shell probe needs `sh` and `python3` in the runner image. Both are in RUNNER_TOOLS.
