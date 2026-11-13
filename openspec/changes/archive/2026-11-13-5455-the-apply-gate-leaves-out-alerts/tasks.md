# Tasks

## 1. Behavior: the gate leaves out the alerts of nodes out of service

- [x] 1.1 Write failing tests: the alert of a node out of service (by `node` or `instance`) is left out with one line; an alert for a node in service, or with no node label, is a problem; the gate before and the wait after a host do not stop for it; the apply ends `ok`, prints the line once and the audit record holds it
  - Verification: `$ uv run devops ci test tests/infra/test_nodes.py tests/commands/test_infra_apply.py`
- [x] 1.2 Filter the alerts in `critical_alerts`, use the filter in `Cluster.health`, `Cluster.alert_health` and `Cluster.wait_alerts_clear`, and add `left_out_alerts` to the apply report, its text footer and its audit record
  - Verification: `$ uv run devops ci test tests/infra/test_nodes.py tests/commands/test_infra_apply.py`

## 2. Documents

- [x] 2.1 Say in the help text of `devops infra apply` which alerts the health checks leave out, and generate the command reference again with `devops docs generate`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The live proof of the issue runs after the merge, from a worktree at `origin/main`: the gVisor apply of the homelab playbook on its node, while the parked node stays in the offline group. No release is necessary for it.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
