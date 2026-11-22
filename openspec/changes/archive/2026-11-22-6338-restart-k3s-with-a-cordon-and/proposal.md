# Proposal

## Why

`devops infra apply` drains a node before each change of class `service-restart:k3s` or `service-restart:k3s-agent`, and the drain check of the control-plane node of homelab can never pass: `k8s/llm/gateway-db.yaml` and `k8s/mattermost/database.yaml` each give `instances: 1`, and their primaries run on that node. A merged k3s or kubelet change therefore never reaches the server node through `devops infra`. A restart of k3s stops only the k3s process and keeps the containers, so the apply needs a cordon, no drain, and the Ready wait and the health check of the control plane (#6338).

## What Changes

- The plan reads the host variable `devops_infra_restart_nodrain_units` beside `devops_infra_nondisruptive_units`, and a changed restart of a listed unit gets the class `service-restart-nodrain:<unit>`; a unit that the nondisruptive list holds keeps no class.
- The cluster gains a cordon call and the apply step enum gains `cordon`, so the report and the audit record name the step that ran.
- The apply cordons a host whose disruptive classes are all no-drain restarts, takes no drain check and no drain, and keeps the fresh check, the run, the Ready wait, the node health, the uncordon of a node that was schedulable before and the alerts.
- A host with any other disruptive class keeps the drain check and the drain before the fresh check.
- The dry run of the apply lists the cordon of a no-drain host and no drain check and no drain.
- The apply and plan help, the generated command pages, `CONTEXT.md`, `SECURITY.md` and the module docstring of the apply module name the class and the steps that it skips.
- A test reads the module docstring, `CONTEXT.md` and `SECURITY.md` and fails when the class or the skipped drain check and drain is missing.
- The spec delta modifies the disruptive classes of `infra-plan` and the one-disruptive-host rule of `infra-apply`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `infra-plan`: The disruptive classes
- `infra-apply`: One disruptive host at a time

## Impact

- Code: `src/devops_cli/infra/plan.py`, `src/devops_cli/models/infra.py`, `src/devops_cli/infra/nodes.py`, `src/devops_cli/infra/apply.py`, `src/devops_cli/infra/infra_plans.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/commands/infra.md`, `docs/CLI_REFERENCE.md`, `CONTEXT.md`, `SECURITY.md`
- Tests: `tests/infra/test_plan.py`, `tests/support/infra.py`, `tests/infra/test_nodes.py`, `tests/commands/test_infra_apply.py`, `tests/infra/test_apply.py`

## Feasibility

- The probes say, word for word: "The path `src/devops_cli/infra/plan.py` is a file of the staging commit." This run read the module with `read_file`, and it holds `PLAN_ACTION: Final[str] = "devops infra plan"` and `SERVICE_RESTART: Final[str] = "service-restart"`.
- The staged constants that the plan relies on are in `src/devops_cli/infra/plan.py`: `NONDISRUPTIVE_UNITS_VARIABLE: Final[str] = "devops_infra_nondisruptive_units"`, `REBOOT: Final[str] = "reboot"` and `DRAIN: Final[str] = "drain"`. The new class takes the shape of `SERVICE_RESTART`, and the plan gives no new name to a bound of a staged constant.
- The class of a restart comes from `return f"{SERVICE_RESTART}:{unit}"` for a unit that the host does not list, and none for a unit that `if unit in units:` matches, in `src/devops_cli/infra/plan.py:def disruptive_class`.
- The read of the nondisruptive list is `value = variables.get(NONDISRUPTIVE_UNITS_VARIABLE)` in `src/devops_cli/infra/plan.py:def nondisruptive_units`, and the new read of the no-drain variable follows it.
- The plan builds its run with `nondisruptive=nondisruptive_units(inventory),` in `src/devops_cli/infra/plan.py`, and the apply builds its run with the same argument, so the new mapping reaches both.
- `read_file` of `src/devops_cli/models/infra.py` showed `class ApplyStep(StrEnum):` with the members `DRAIN_CHECK = "drain check"`, `DRAIN = "drain"` and `UNCORDON = "uncordon"`, in run order.
- The probes say, word for word: "The path `k8s/llm/gateway-db.yaml` is a file of the staging commit." and "The path `k8s/mattermost/database.yaml` is a file of the staging commit." Each staged file gives `instances: 1` under `spec:`, so each CloudNativePG cluster runs one instance, and a drain of the node that runs its primary needs an eviction that its budget refuses.
- The probes say, word for word: "The path `ansible/playbooks/03_k3s.yaml` is no file at the root of the staging commit. These files of the commit are candidates: `tests/fixtures/infra/homelab_shape/ansible/playbooks/03_k3s.yaml`. No commit in the history deleted or renamed it." That playbook belongs to the homelab infra repo, and no group changes a playbook, so the premise stands and no code compensates for it.
- The one-host path runs `for step in (_drain, _change, _settle):` in `src/devops_cli/infra/apply.py:def _apply_alone`, and its drain step runs `if (problem := cluster.drain_check(work.node)) is not None:` before the fresh check; that is the drain that the issue reports.
- `src/devops_cli/infra/apply.py:def _prepare` reads the inventory with `inventory = read_inventory(tool, project, sources)` and builds the run with `nondisruptive=nondisruptive_units(inventory),`, so the fresh check of a no-drain host gives its plan again once the apply passes the new mapping the same way.
- `src/devops_cli/infra/infra_plans.py:def _host_steps` sets `timeout = target.drain_timeout_seconds` and lists the pods, the claims, the volumes, the server dry run of the drain and the drain of one disruptive host.
- `src/devops_cli/infra/nodes.py:class Cluster` defines `drain`, `drain_check`, `uncordon`, `wait_ready`, `wait_nodes_healthy` and `wait_alerts_clear`, and `src/devops_cli/infra/nodes.py:def uncordon` runs `read = self._kubectl(uncordon_args(node), DEFAULT_INFRA_KUBECTL_TIMEOUT_SECONDS)`.
- The cordon that this change adds needs a client of the cluster and a network to its API server, and the uncordon, the drain and the drain check of a node need the same.
- The run of the playbook needs a checkout of the infra repo at the commit of the plan and a network to the hosts, and the reads and the waits of the apply need a client of the cluster and a network to its API server. The tests answer each of those calls through the fake process and the fake cluster, so no test reaches a host, a cluster or a network.
- The review finding is a defect and this plan corrects it: group 6 no longer verifies with `uv run devops ci docs`, which compares only the generated command pages, and runs `uv run devops ci test tests/infra/test_apply.py` instead. The new test reads the docstring of `src/devops_cli/infra/apply.py`, where `6. **One disruptive node at a time.** The hosts with no disruptive class run together in one run.` names the step list that the group edits, and reads `CONTEXT.md` and `SECURITY.md` from `REPO_ROOT` of `tests/support/paths.py`; it fails when the class or the skipped drain check and drain is missing.
- The plan adds no command and no program of its own. The verify commands are `uv run devops ci test <path>` and `uv run devops ci docs`: they run `uv`, `devops` and `pytest` of the runner image, and a failing test is the failure class `test`, a stale generated page the failure class `lint`. The new test reads repository files and needs no checkout, client or network.
- No test starts ansible: `ansible-core` is NOT_IN_RUNNER, and the fake process and the fake cluster answer every call, under the pod settings allowPrivilegeEscalation false, capabilities drop ALL, runAsNonRoot true, seccompProfile RuntimeDefault and readOnlyRootFilesystem true.
- The first live checks are `uv run devops infra plan dan-petty/homelab ansible/playbooks/03_k3s.yaml --limit <control-plane-node>`, which must show `service-restart-nodrain:k3s` for a host that lists `k3s` in `devops_infra_restart_nodrain_units`, and `kubectl get pdb -A`, which must still show the two budgets at 0 disruptions.
- not checked: the `KillMode=process` of the k3s units and the 0 disruptions of the two PodDisruptionBudgets, which live in the homelab repo and its cluster; the plan relies on the issue for them and changes no unit file and no database manifest.
- not checked: the state of #5267 and #6731, which the issue body names; this change delivers the class in the infra documents itself with a test, so it depends on neither.

## Existing Tool Considered

rancher/system-upgrade-controller (Apache-2.0, last activity 2026-11-21) cordons the server node and restarts k3s with no drain, but it upgrades k3s versions only, runs no playbook of the repository and joins no apply step class, so it covers none of the apply path that this change needs. The change extends the apply step list of devops-cli itself: about 40k tokens to build, keep and fix it, and about 2 hours of elapsed time.

## Dependencies

None.
