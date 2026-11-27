# Tasks

## 1. Let an agent apply a no-drain restart of a control-plane node

Kind: behavior. Reads: `src/devops_cli/infra/apply.py`, `src/devops_cli/infra/plan.py`, `src/devops_cli/infra/access.py`, `tests/commands/test_infra_apply.py`, `tests/support/infra.py`. Changes: `src/devops_cli/infra/apply.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_infra_apply.py`.

- [x] 1.1 Write `test_an_agent_at_full_applies_a_nodrain_restart_of_the_control_plane_node` in `tests/commands/test_infra_apply.py` first, for the scenario A no-drain restart of the control-plane node: node-1 has the control-plane label and lists its demo unit in `devops_infra_restart_nodrain_units`, and an agent at full applies the plan of node-1 with the steps cordon node-1, check, run and uncordon node-1. Make the stop test `test_an_agent_stops_before_a_drain_or_a_reboot_of_the_control_plane_node` take a drain class on node-1 and a reboot on node-2, and assert the reason names the no-drain restart. Add `test_an_agent_at_safe_is_refused_a_nodrain_restart_of_the_control_plane_node` for the scenario An agent at safe and a no-drain restart of the control-plane node
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py` fails on the base
- [x] 1.2 In `_apply_alone` of `src/devops_cli/infra/apply.py`, stop an agent at a control-plane node only when `skips_drain` is false for the host, and keep the stop at the node of its own pod. Say in `apply_role_control_plane` of `src/devops_cli/lang/en/messages.py` that an agent changes a control-plane node only with a no-drain restart
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py` passes

## 2. Say which control-plane changes an agent applies

Kind: other. Reads: `src/devops_cli/lang/en/help.py`, `src/devops_cli/infra/apply.py`, `SECURITY.md`, `CONTEXT.md`. Changes: `src/devops_cli/lang/en/help.py`, `src/devops_cli/infra/apply.py`, `docs/commands/infra.md`, `docs/CLI_REFERENCE.md`, `SECURITY.md`, `CONTEXT.md`.

- [x] 2.1 Say in the apply help of `src/devops_cli/lang/en/help.py`, in the module docstring of `src/devops_cli/infra/apply.py`, in the access levels of `SECURITY.md` and in the term Infra apply of `CONTEXT.md` that an agent stops before the node of its own pod and applies on a control-plane node only a host whose disruptive classes are all `service-restart-nodrain:<unit>`. Then run `uv run devops docs generate`, which writes `docs/commands/infra.md` and `docs/CLI_REFERENCE.md`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
