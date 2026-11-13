# Design

## Decisions
- **The node of an alert is its label `node`, else its label `instance`.** kube-state-metrics series carry `node`, and the homelab node rules copy `instance` into `node`. An alert of node-exporter with no `node` label names its node in `instance`. The label `node` comes first, so an alert for a node in service with an `instance` that names a node out of service still stops the gate. The compare is an exact match on the node name. The `instance` of a scrape target that is an address with a port never equals a node name, so such an alert stays a problem.
- **`critical_alerts` returns `Alerts(problems, left_out)`.** The function stays pure over one query answer. `Cluster.alert_health` gives each left-out line to the callback `on_left_out`, and `Cluster.health` calls `alert_health`, so the gate before the apply and the wait after each host use one filter.
- **The apply keeps each line once.** The wait after a host reads the alerts on each poll, so the same line comes again. `_Progress.leave_out` keeps a line only when it is new. The report field `left_out_alerts` holds the lines, the text report prints them under the result line, and the audit record holds them. The report is the place where the apply already names what it did not stop for (`down_during_apply`).
- **The domain module does not print.** ARCHITECTURE.md (section 6) keeps the print in the commands, and the domain packages give values. The command prints the report of the apply. The audit record keeps the lines for an apply of an agent.

## Rejected alternatives
- **Print each left-out alert to standard error from `Cluster`.** Rejected: the domain package does not print (ARCHITECTURE.md, section 6), and the wait gives the line on each poll, so the output repeats.
- **Add `node!~"<offline nodes>"` to the PromQL query.** Rejected: Prometheus then does not return the alert, so the gate cannot name what it left out, and the issue asks that the apply names each one.
- **Use an Alertmanager silence for the parked node.** Rejected: a silence acts on notifications. The `ALERTS` series in Prometheus still fires, and the gate reads Prometheus.
- **Leave out every alert while any node is out of service.** Rejected: the issue asks that an alert with no node label, or for another node, still stops the apply.
