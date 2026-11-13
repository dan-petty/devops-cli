# Proposal: #5455

## Why
The health gate of `devops infra apply` leaves out the nodes of the hosts out of service (the offline group of the profile) when it reads the nodes, but it reads every firing critical alert. So the alert of a parked node stops each apply in the cluster. On 2026-11-13 a parked node in the offline group fired `NodeNotReady`, and the gVisor apply on another node stopped with "the critical alert NodeNotReady fires" (#5455).

## What Changes
- `critical_alerts` takes the nodes out of service. It leaves out each firing critical alert whose label `node`, else whose label `instance`, names one of them, and gives one line for each alert that it leaves out. An alert with no such label, or for a node in service, is a problem as before.
- `Cluster.health`, `Cluster.alert_health` and `Cluster.wait_alerts_clear` use this filter, so the gate before the apply does not stop and the wait after a host does not hold until its bound for the alert of a parked node.
- The apply report has the new field `left_out_alerts`: one line for each alert left out, once. The text report prints each line under the result line. The audit record `infra.apply` holds the field.
- The help text of `devops infra apply` says which alerts the health checks leave out. The command reference is generated again.

This is a fix of the gate behavior that a consumer sees (a message, a field of the report and of the audit record), so the change has a spec delta.

## Capabilities
- `infra-apply`: the new requirement "The health gate leaves out the alerts of the nodes out of service", and the changed requirement "Each apply writes an audit record". The requirement "The cluster is healthy before the apply" does not change: the new requirement narrows which alerts it reads.

## Impact
- Users of `devops infra apply`: a parked node in the offline group no longer stops an apply on other nodes through its own alerts. Every other critical alert still stops the apply.
- JSON output and the audit record get one more field. No setting changes.
- The fix needs no release for the live proof: the operator runs `devops` from a worktree at `origin/main` after the merge.
- The change fits one pull request.

## Feasibility
- Source at `origin/main` (0341ae1fd): `Cluster.node_health` in `src/devops_cli/infra/nodes.py` leaves out `offline_nodes`, but `critical_alerts` takes only the settings and turns each series of `ALERTS{alertstate="firing",severity="critical"}` into a problem. `Cluster.health` and `Cluster.wait_alerts_clear` call it with no node filter.
- The alert carries the node: the rule `NodeNotReady` in `k8s/monitoring/prometheus-values.yaml` is `kube_node_status_condition{condition="Ready", status="true"} == 0`, and kube-state-metrics puts the label `node` on that series. The node rules of node-exporter set `node: "{{ $labels.instance }}"`, and node-exporter names its node in `instance`.
- A live read of the gate query `ALERTS{alertstate="firing",severity="critical"}` through the Grafana Prometheus data source on 2026-11-13 gave one series: `NodeNotReady` with `node` set to the parked node and `instance` set to the address of the kube-state-metrics Service. So the label `node` names the parked node, and the label `instance` of that series names no node.
- `devops infra apply` builds `offline_nodes` from the offline group of the inventory with `node_name` (`src/devops_cli/infra/apply.py`), so the alert labels compare with the same node names.
- The new command test reproduces the live stop on the base: "The cluster is not healthy, so the apply starts no host: the critical alert NodeNotReady fires".
- The issue also says that the plan names the left-out alerts. `devops infra plan` (`src/devops_cli/infra/plan.py`) has no health gate and reads no alert, so only the apply names them.

## Existing Tool Considered
The Prometheus query result labels that the gate already reads, and Alertmanager silences. A silence does not change the `ALERTS` series that Prometheus gives, so the gate still sees the alert; only the labels of the query result can leave it out. No new tool or library. The change deletes no internal code. Cost to build: about 0.15 M tokens and 1 hour, as the issue estimates.
