# Design

## Decisions
- **Open before the drain check, close after the uncordon**: The node stays cordoned through the fresh check, the run and the health of the nodes, so the Cluster must stay down until the uncordon. Opening only around the drain would cause the operator to attempt scheduling the primary while the node is still cordoned.
- **Refuse the host when git has the field or when Argo CD selfHeal lacks ignoreDifferences**: If `nodeMaintenanceWindow` is committed in git or if Argo CD `selfHeal` is enabled without an `ignoreDifferences` entry for `/spec/nodeMaintenanceWindow`, Argo CD would immediately revert the patch during the apply. Refusing the host and directing the user to add an `ignoreDifferences` entry maintains GitOps integrity without disabling cluster-wide `selfHeal`.
- **Require agent access full**: Changing the state of a database cluster is an infrastructure modification that requires `full` access level when run by an agent.
- **Wait for Cluster in healthy state with primary Ready bounded by infra.node_ready_timeout_seconds**: Ensures the database cluster recovered before running later steps or hosts. A timeout stops the host.
- **Add windowed clusters to down_during_apply in the audit record**: Surfaces the database downtime in the audit record and apply output alongside local-volume workloads.
- **Dry-run lists reads and patches**: Lists the cluster reads and maintenance window patch commands in plan order without executing them.

## Rejected alternatives
- **Set spec.enablePDB: false**: Removes disruption budget protection for all drains, including unplanned reboots.
- **Disable selfHeal in Argo CD**: Modifies shared application configuration from the CLI and could hide subsequent configuration drifts.
- **Pause auto-sync during the window**: Leaves the application paused if the apply aborts midway.
- **Install kubectl-cnpg plugin**: Adds a heavy external binary dependency when `kubectl patch` natively accomplishes the merge patch.

## Security
Patches are executed only through the configured kube context. An agent must have `full` access level to trigger a disruptive apply and open maintenance windows. No credentials or secrets are written or logged.
