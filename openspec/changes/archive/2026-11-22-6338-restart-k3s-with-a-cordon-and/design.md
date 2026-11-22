# Design

## Decisions

- **Cordon the node, restart the unit, wait for Ready and the health of the nodes, and uncordon a node that was schedulable before. Do not drain.**: A k3s restart stops only the k3s process and keeps the containers, and the drain check of the control plane cannot pass. This path keeps the Ready wait and the health check of the control plane.
- **Select the units per host with a new host variable, devops_infra_restart_nodrain_units, read beside devops_infra_nondisruptive_units.**: The selection stays in the inventory of the infra repo, as the nondisruptive list does, so another infra repo chooses its own units.
- **The nondisruptive list wins when a host lists a unit in both variables.**: A unit whose restart does not disrupt the host needs neither a drain nor a cordon, so the weaker class holds.
- **The apply takes one path with a selected step list: a host whose disruptive classes are all no-drain restarts runs cordon, fresh check, run, Ready, health, uncordon and alerts; every other disruptive host keeps the drain check and the drain.**: The fresh check, the settle steps and the report stay in one place, and a host that mixes a no-drain restart with a reboot still drains.
- **Add the member cordon to the apply step enum and never reuse the drain step.**: The report and the audit record then name the step that ran, and no drain is reported for a host that did not drain.
- **A no-drain restart runs neither the drain check nor the drain.**: No eviction happens, and the server dry run can reach its timeout on a PodDisruptionBudget that does not apply, as the evidence of the issue shows.
- **The predicate skips_drain sits in the plan module beside the class constants, and the apply and the dry run import it.**: The plan, the apply and the dry run then decide alike, and the dry run imports no apply module.
- **The playbook of a plan gains a nodrain mapping that defaults to no unit, and the apply passes the units of the inventory into it.**: The plan-side change stands alone, and the fresh check of a no-drain host reads the same variable that the plan read.
- **Name the class in the Infra apply term of CONTEXT.md here, and let a test read the term, rather than leave the term to #6731.**: The acceptance criterion of #6338 asks the infra documents to name the class, and `tests/invariants/test_agents_md.py` shows that a test reads a root Markdown document, so the reason that moved the term to #6731 does not hold.

## Rejected alternatives

- **Reuse devops_infra_nondisruptive_units for the k3s units.**: The read of that list gives such a unit no class, because `if unit in units:` returns none, so the host runs in the together run with no cordon, no Ready wait and no health check after the restart.
- **Wait for the CloudNativePG maintenance window of #5267 around the drain.**: A reboot-class change needs the eviction, and a k3s restart does not: the units use `KillMode=process`, so no pod of the node stops.
- **Set spec.enablePDB: false on the two single-instance clusters.**: That removes the protection of the primary for each drain, a reboot included, and the issue asks for no such loss.
- **Hard-code k3s and k3s-agent as the no-drain units.**: Another infra repo could not choose its own units, and the read of the nondisruptive list already keeps that choice in the inventory.
- **Give the apply a second path for no-drain hosts.**: It duplicates the fresh check, the settle steps and the report of `_apply_alone`, which runs `for step in (_drain, _change, _settle):` for each disruptive host.
- **Put a flag inside the drain step.**: The report of the host would still name a drain step for a host that did not drain.
- **Keep the drain check of a no-drain host.**: The issue records that the server dry run reached its timeout on the control-plane node, so the check stops the apply before the restart.
- **Leave the CONTEXT.md term of the class to #6731 and name the class only in the module text.**: The acceptance criterion of #6338 names the infra documents, and `tests/invariants/test_agents_md.py` reads `AGENTS.md` from `REPO_ROOT`, so a test can assert the term and the term belongs to this change.

## Security

Nothing new crosses a trust boundary: the apply still runs kubectl of the kube context of the entry and Ansible over SSH with the key of devops ssh, and an agent still needs the level full for a plan with a disruptive class. A no-drain host skips the drain check, which is the only guard that reads the PodDisruptionBudgets before a host changes, so a person must confirm that a host lists in devops_infra_restart_nodrain_units only units whose restart stops no container, such as k3s and k3s-agent under KillMode=process. The test test_a_nodrain_restart_cordons_the_node_and_skips_the_drain fails if a no-drain host reaches the drain check or the drain, and test_each_disruptive_host_drains_runs_and_uncordons_alone_in_plan_order fails if a host with any other disruptive class loses them.
