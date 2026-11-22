# Tasks

## 1. Give a listed no-drain unit restart its own class

Kind: behavior. Reads: `src/devops_cli/infra/plan.py`, `src/devops_cli/models/infra.py`, `tests/infra/test_plan.py`, `tests/commands/test_infra_plan.py`, `tests/infra/test_apply.py`, `tests/infra/test_nodes.py`, `tests/infra/test_onboard.py`, `tests/infra/test_repo_tree.py`, `tests/infra/test_status.py`. Changes: `src/devops_cli/infra/plan.py`, `src/devops_cli/models/infra.py`, `tests/infra/test_plan.py`.
Adds: `NODRAIN_UNITS_VARIABLE`, `SERVICE_RESTART_NODRAIN`, `nodrain_units`, `skips_drain`

- [x] 1.1 Write `test_a_unit_that_the_host_lists_for_a_nodrain_restart_gets_the_nodrain_class` in `tests/infra/test_plan.py` first, for the scenario A unit that the host lists for a no-drain restart: the host events of node-3 with the no-drain mapping that holds k3s-agent give node-3 the class service-restart-nodrain:k3s-agent and no other disruptive class. Then write `test_a_templated_nodrain_list_lists_no_unit` for the scenario A templated list of no-drain units: a host variable that holds `{{ units }}` lists no unit, so every restart stays disruptive
  - Verification: `$ uv run devops ci test tests/infra/test_plan.py` fails on the base
- [x] 1.2 Add the constant NODRAIN_UNITS_VARIABLE with the value devops_infra_restart_nodrain_units and the constant SERVICE_RESTART_NODRAIN with the value service-restart-nodrain to `src/devops_cli/infra/plan.py`, a nodrain_units read beside nondisruptive_units, and a skips_drain predicate that is true when a host has a class and each of its classes starts with SERVICE_RESTART_NODRAIN. Pass the no-drain mapping through host_plans and _add to disruptive_class, with a default of no unit so an existing caller changes nothing; disruptive_class gives service-restart-nodrain:<unit> for a listed unit and keeps the nondisruptive list first. Add a nodrain field to Playbook that defaults to no unit, and pass nodrain=nodrain_units(inventory) where the plan builds its Playbook. Name the new class in the description of the disruptive field of `src/devops_cli/models/infra.py`
  - Verification: `$ uv run devops ci test tests/infra/test_plan.py` passes

## 2. Add the cordon step to the cluster

Kind: behavior. Reads: `src/devops_cli/infra/nodes.py`, `src/devops_cli/models/infra.py`, `tests/support/infra.py`, `tests/infra/test_nodes.py`, `tests/infra/test_apply.py`, `tests/infra/test_onboard.py`, `tests/infra/test_plan.py`, `tests/infra/test_repo_tree.py`, `tests/infra/test_status.py`. Changes: `src/devops_cli/models/infra.py`, `src/devops_cli/infra/nodes.py`, `tests/support/infra.py`, `tests/infra/test_nodes.py`.
Adds: `CORDON`, `cordon_args`, `cordon`

- [x] 2.1 Write `test_a_cordon_leaves_the_node_cordoned` in `tests/infra/test_nodes.py` first: a cordon of node-1 through the cluster gives no problem, the fake records the step cordon node-1, the node reads as cordoned after it, and a later uncordon makes it schedulable again
  - Verification: `$ uv run devops ci test tests/infra/test_nodes.py` fails on the base
- [x] 2.2 Add the member CORDON to ApplyStep in `src/devops_cli/models/infra.py`, in run order before the fresh check, and describe it as the step that takes the place of the drain check and the drain. Add cordon_args beside uncordon_args in `src/devops_cli/infra/nodes.py` and a cordon method on the cluster that runs it through _kubectl with the kubectl timeout and gives the problem of the read, as uncordon does. Answer a cordon in `tests/support/infra.py`: it sets the node cordoned and records the step, as a drain does
  - Verification: `$ uv run devops ci test tests/infra/test_nodes.py` passes

## 3. Cordon a no-drain host instead of draining it

Kind: behavior. Reads: `src/devops_cli/infra/apply.py`, `src/devops_cli/infra/plan.py`, `tests/commands/test_infra_apply.py`, `tests/support/infra.py`, `tests/infra/test_apply.py`. Changes: `src/devops_cli/infra/apply.py`, `tests/commands/test_infra_apply.py`.
Adds: `_cordon`

- [x] 3.1 Write `test_a_nodrain_restart_cordons_the_node_and_skips_the_drain` in `tests/commands/test_infra_apply.py` first, for the scenario A no-drain restart of a host of the requirement One disruptive host at a time: the test answers the inventory read again with a recorded listing whose hostvars of node-3 hold devops_infra_restart_nodrain_units with k3s-agent, plans node-3, applies the plan, and asserts the steps cordon node-3, check node-3, run node-3 and uncordon node-3 with no drain check and no drain; a second case whose node-3 was cordoned before ends with the node still cordoned
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py` fails on the base
- [x] 3.2 Add a _cordon step to `src/devops_cli/infra/apply.py` that cordons the node and stops at ApplyStep.CORDON on a problem, and let _apply_alone run the cordon, the fresh check and the settle steps for a host that skips_drain names, and the drain, the fresh check and the settle steps for each other disruptive host. A read of the node that fails stops at the step CORDON for a no-drain host and at DRAIN_CHECK otherwise. Pass nodrain=nodrain_units(inventory) to the Playbook in _prepare, so the fresh check of a no-drain host gives its plan again
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py` passes

## 4. List the cordon in the dry run of a no-drain host

Kind: behavior. Reads: `src/devops_cli/infra/infra_plans.py`, `src/devops_cli/infra/plan.py`, `tests/commands/test_infra_apply.py`. Changes: `src/devops_cli/infra/infra_plans.py`, `tests/commands/test_infra_apply.py`.

- [x] 4.1 Write `test_a_dry_run_of_a_nodrain_host_lists_the_cordon_and_no_drain` in `tests/commands/test_infra_apply.py` first, for the scenario The dry run of a no-drain host of the requirement One disruptive host at a time: after a plan of node-3 whose hostvars hold devops_infra_restart_nodrain_units with k3s-agent, the dry run lists the cordon of node-3 with the condition that the node was schedulable before, and lists no pods, no claims, no volumes, no drain check and no drain
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py` fails on the base
- [x] 4.2 Hand the disruptive classes of each host to _host_steps of `src/devops_cli/infra/infra_plans.py`, and list the cordon of the node, with the condition of a node that was schedulable before, for a host that skips_drain names, in place of the pods, the claims, the volumes, the server dry run of the drain and the drain. Import skips_drain from the plan module, so the dry run and the apply decide alike and no apply module is imported
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py` passes

## 5. Name the class in the apply and plan help and the generated pages

Kind: other. Reads: `src/devops_cli/lang/en/help.py`, `docs/commands/infra.md`, `docs/CLI_REFERENCE.md`, `tests/lang/test_language_catalogs.py`. Changes: `src/devops_cli/lang/en/help.py`, `docs/commands/infra.md`, `docs/CLI_REFERENCE.md`.

- [x] 5.1 Name the class service-restart-nodrain:<unit>, the cordon and the skipped drain check and drain in the apply help and the plan help of `src/devops_cli/lang/en/help.py`, which list the disruptive changes today. Then run uv run devops docs generate, which writes `docs/commands/infra.md` and `docs/CLI_REFERENCE.md` from the command tree, and never edit those two pages by hand
  - Verification: `$ uv run devops ci docs` passes
- [x] 5.2 Edit `src/devops_cli/lang/en/help.py` and regenerate `docs/commands/infra.md` and `docs/CLI_REFERENCE.md`, and run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## 6. Name the class in the apply module text and the infra documents

Kind: other. Reads: `src/devops_cli/infra/apply.py`, `CONTEXT.md`, `SECURITY.md`, `tests/infra/test_apply.py`, `tests/support/paths.py`, `tests/commands/test_infra_apply.py`. Changes: `src/devops_cli/infra/apply.py`, `CONTEXT.md`, `SECURITY.md`, `tests/infra/test_apply.py`.

- [x] 6.1 Name the class service-restart-nodrain:<unit>, the cordon and the skipped drain check and drain in the docstring of `src/devops_cli/infra/apply.py`, in the terms Infra apply and Disruptive class of `CONTEXT.md`, and in the guards of `SECURITY.md`, which must say that a host of the class skips the only check that reads the PodDisruptionBudgets before a host changes. Add `test_the_apply_module_text_names_the_nodrain_class` to `tests/infra/test_apply.py`: it reads the docstring of devops_cli.infra.apply and reads `CONTEXT.md` and `SECURITY.md` from REPO_ROOT of `tests/support/paths.py`, and it asserts that each names service-restart-nodrain and that the docstring states that the drain check and drain are skipped
  - Verification: `$ uv run devops ci test tests/infra/test_apply.py` passes
- [x] 6.2 Edit `CONTEXT.md`, `SECURITY.md` and the module docstring of `src/devops_cli/infra/apply.py` to name the class, the cordon and the steps that it skips
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A plan test: a changed restart of a unit that the host lists for a restart with no drain gets that class.
- Group 3: An apply test with a fake cluster: a host of that class is cordoned, not drained, waits for Ready, and is uncordoned only when it was schedulable before.
- Group 6: The module text of `src/devops_cli/infra/apply.py` and the infra documents name the class.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
