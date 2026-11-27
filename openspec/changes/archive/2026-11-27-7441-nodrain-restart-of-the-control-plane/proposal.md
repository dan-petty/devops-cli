# Proposal: #7441

## Why

`devops infra apply` stops an agent before each disruptive host on a control-plane node, also when each disruptive class of the host is `service-restart-nodrain:<unit>` (#7441). A no-drain restart cordons the node and keeps its containers: the k3s units of dan-petty/homelab use `KillMode=process`. The owner decided on 2026-11-27 that agents run the node steps of dan-petty/homelab in a maintenance window. So the stop keeps one step with a person that the owner gave to agents: each play that changes the k3s server config, such as dan-petty/homelab#558.

## What Changes

- At the agent access level `full`, an agent applies a control-plane host whose disruptive classes are all `service-restart-nodrain:<unit>`: the cordon, the fresh check, the run, the Ready and health waits, the uncordon and the alerts, as for a person.
- An agent still stops before a control-plane host with any other disruptive class (`reboot`, `service-restart:<unit>` or `drain`), because the apply drains or reboots that node. The stop at the node of the agent's own pod stays.
- The stop reason of a control-plane host says that an agent changes a control-plane node only with a no-drain restart.
- The apply help, the generated command pages, `SECURITY.md`, `CONTEXT.md` and the module docstring of the apply module say which control-plane changes an agent applies.
- The access-level check does not change: each disruptive class, a no-drain restart included, needs `full`. The change adds no flag and no setting.
- The spec delta modifies the requirement "Stop before own node and control-plane node" of `infra-apply`, because the apply command and the step job share the stop.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `infra-apply`: Stop before own node and control-plane node

## Impact

- Code: `src/devops_cli/infra/apply.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/commands/infra.md`, `docs/CLI_REFERENCE.md`, `SECURITY.md`, `CONTEXT.md`
- Tests: `tests/commands/test_infra_apply.py`
- The `infra-apply` step job calls the same apply, so after a merge of an infra repo at `full` it also applies a no-drain restart of a control-plane node.

## Feasibility

- On `origin/main` at `caf276a93`, `src/devops_cli/infra/apply.py:645` reads `if cluster.is_control_plane(work.node):` inside `if context.caller.is_agent:` of `_apply_alone`, before any class check. The new test `test_an_agent_at_full_applies_a_nodrain_restart_of_the_control_plane_node` fails there with the reason "node-1.example.com stopped at the step cordon: The host node-1.example.com (node-1) is the control-plane node".
- `skips_drain` in `src/devops_cli/infra/plan.py` is true only when a host has a class and each class starts with `service-restart-nodrain:`. Its test `test_a_host_skips_the_drain_only_when_each_of_its_classes_is_a_nodrain_restart` holds the case `nodrain-and-reboot` as false. The apply already uses it to choose the cordon in place of the drain, so the stop and the steps decide alike.
- The set of disruptive classes is closed: `src/devops_cli/infra/plan.py:107-110` gives `reboot`, `drain`, `service-restart` and `service-restart-nodrain`, 4 classes. The change allows only the last one on a control-plane node.
- `apply_level` in `src/devops_cli/infra/access.py` gives `full` for each host with a disruptive class, so an agent that reaches the stop of `_apply_alone` is at `full`. The stop needs no second level check.
- `uv run devops infra plan dan-petty/homelab ansible/playbooks/03_k3s.yaml --limit k3s_server` (read-only check mode, homelab `origin/main` at `19668f2`) shows the one server host with 3 changed tasks and the one disruptive class `service-restart-nodrain:k3s`.
- `ansible/inventory/group_vars/k3s_cluster.yaml` of dan-petty/homelab lists `k3s` and `k3s-agent` in `devops_infra_restart_nodrain_units`, with the note that the k3s installer writes both units with `KillMode=process`.
- The waits read again through a restart of the API server: `test_the_waits_go_on_through_a_restart_of_the_api_server` runs the same `_settle` step that a no-drain host runs.

## Existing Tool Considered

The stop is a guard of devops-cli itself, so no open tool covers it. rancher/system-upgrade-controller (Apache-2.0) cordons a server node and restarts k3s with no drain, but it only upgrades the k3s version and runs no playbook of the repository. The change edits one condition of the existing guard and its texts: about 30k tokens to build and keep, and about 1 hour of elapsed time. It deletes no internal code.
