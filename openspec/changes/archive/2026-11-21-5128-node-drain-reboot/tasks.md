# Tasks

## 1. The node commands

Kind: behavior. Reads: `src/devops_cli/infra/nodes.py`, `src/devops_cli/infra/apply.py`, `src/devops_cli/infra/status.py`, `src/devops_cli/infra/infra_plans.py`, `tests/support/infra.py`. Changes: `src/devops_cli/infra/node_run.py`, `src/devops_cli/infra/ad_hoc.py`, `src/devops_cli/infra/nodes.py`, `src/devops_cli/infra/status.py`, `src/devops_cli/infra/plan.py`, `src/devops_cli/infra/infra_plans.py`, `src/devops_cli/models/infra.py`, `src/devops_cli/commands/infra.py`, `src/devops_cli/exceptions/infra.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/lang/en/`, `tests/support/infra.py`, `tests/commands/test_infra_node.py`, `tests/infra/test_ad_hoc.py`, `tests/infra/test_nodes.py`, `tests/infra/test_plan.py`.

- [x] 1.1 Write the failing tests of each scenario of `infra-node` with the fake kubectl of `FakeCluster` and a fake ad-hoc ansible-runner that both write each step in one list: the order of the steps of each operation, the drain bound, `--force` from a person and from an agent, a host that the inventory does not have, a cordoned node that stays cordoned, a restart with no unit and with a template unit, both kernels of a reboot and the wait for a new boot ID, the stop before the second host, a failed Ready wait, the levels, the audit record and the counter, and the dry run with no process
  - Verification: `$ uv run devops ci test tests/commands/test_infra_node.py tests/infra/test_ad_hoc.py tests/infra/test_nodes.py` fails on the base
- [x] 1.2 Add `infra/ad_hoc.py` (`ad_hoc_argv`, `AdHoc.run`, and `tool_env` and `read_job_events` moved from `status.py` and `plan.py`), and run the SSH check of `devops infra status --ping` with it; add `force` to `drain_args` and the drain of `Cluster`, and the boot ID wait to `Cluster.wait_ready`; add `infra/node_run.py`, the node models, `InfraNodeRefusedError`, the defaults, the dry-run plan `plan_node`, the texts and the command group `devops infra node`
  - Verification: `$ uv run devops ci test tests/commands/test_infra_node.py tests/infra tests/commands/test_infra_apply.py tests/commands/test_infra_status.py`

## 2. Documents

Kind: other. Changes: `CONTEXT.md`, `SECURITY.md`, `docs/HOMELAB_REPO_SWITCH.md`, `docs/TELEMETRY.md`, `docs/CLI_REFERENCE.md`, `docs/commands/infra.md`, `docs/ERRORS.md`.

- [x] 2.1 Add the term "Node command" to CONTEXT.md, name the uncordon at `safe` and the guards of the node commands in `## Infra Repos` of SECURITY.md, add the node command values of `devops_cli_infra_runs_total` to docs/TELEMETRY.md, and regenerate the command reference and the error table with `devops docs generate`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Live runs of the acceptance criteria, when the host of the acceptance criteria is back in service. The runs do not need the merge, because the command reads the inventory at the default branch of dan-petty/homelab. Since 2026-11-13 the host is in the group `offline` of that inventory, and the command refuses a host of that group. The runs: `devops infra node reboot dan-petty/homelab <host>` at the level `full` by an agent, after the crash-capture apply of dan-petty/homelab#20, with the kernel before and after, 1 GPU allocatable, the node cordoned after, and `/sys/kernel/kexec_crash_size` above 0; and `devops infra node restart dan-petty/homelab <host>`, Ready and cordoned after. Record the audit records in a comment of the pull request.
- dan-petty/homelab#22 removes the per-host Makefile targets and `rolling-restart`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
