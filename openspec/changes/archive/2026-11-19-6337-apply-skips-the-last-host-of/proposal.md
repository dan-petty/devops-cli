# Proposal

## Why

`devops infra apply` skips the last host of a run of hosts with no disruptive class, so that host keeps its old state and the run leaves the cluster inconsistent. `host_pattern` appends `:!<offline group>` to the limit, and Ansible splits a pattern that holds a comma on the commas only, so the term `<last host>:!offline` matches no host and the exclusion applies to none of the run (#6337).

## What Changes

- `host_pattern` joins the offline exclusion with a comma when the limit holds a comma and with a colon when it holds none, so each host of a comma limit stays one term.
- The together run of an apply sends a limit in which each host and the offline exclusion are separate comma terms, so Ansible reaches every host of the plan and no host of the offline group.
- The dry-run text of the plan command and of the apply command shows the separator that the run sends, through the same helper.
- The fake runner reads the hosts of a run from its limit with each `!` term dropped, so it reads the comma form as well as the colon form.
- Tests cover the helper, the plan dry run, the apply dry run and the limit of a together run of two hosts.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `infra-plan`: No host of the offline group is in the limit
- `infra-apply`: Each host of the together run is one term of the limit

## Impact

- Code: `src/devops_cli/infra/plan.py`, `src/devops_cli/infra/infra_plans.py`
- Tests: `tests/infra/test_plan.py`, `tests/commands/test_infra_plan.py`, `tests/commands/test_infra_apply.py`, `tests/support/infra.py`

## Feasibility

- The probe confirms the helper's file: "The path `src/devops_cli/infra/plan.py` is a file of the staging commit.", and `read_file` showed `def host_pattern(limit: str | None, offline_group: str | None) -> str:` with the colon of the issue at `src/devops_cli/infra/plan.py:168:return f"{pattern}:!{offline_group}" if offline_group else pattern`.
- The pattern of a run with no limit comes from `src/devops_cli/infra/plan.py:167:pattern = limit or _ALL_HOSTS` and `src/devops_cli/infra/plan.py:105:_ALL_HOSTS: Final[str] = "all"`, and the plan command passes the limit to the helper at `src/devops_cli/infra/plan.py:592:pattern = host_pattern(request.limit, ansible.offline_group)`.
- The probe confirms the together run's file: "The path `src/devops_cli/infra/apply.py` is a file of the staging commit.", and `read_file` showed `def _apply_together(context: _Context, hosts: list[HostPlan])` joining the names at `src/devops_cli/infra/apply.py:554:names = ",".join(host.host for host in hosts)` and running them at `src/devops_cli/infra/apply.py:555:outcome = context.run.run(host_pattern(names, context.offline_group), check_mode=False)`.
- The probe confirms the dry-run file: "The path `src/devops_cli/infra/infra_plans.py` is a file of the staging commit.", and `read_file` showed `def plan_plan(` and `def plan_apply(target: ApplyTarget) -> list[PlannedRequest]:` holding the literals `src/devops_cli/infra/infra_plans.py:182:pattern=f"{limit or 'all'}:!<offline group>",` and `src/devops_cli/infra/infra_plans.py:281:argv=runner(f"{','.join(together)}:!<offline group>", check_mode=False),`.
- The steps of one disruptive host keep the colon, `src/devops_cli/infra/infra_plans.py:320:pattern = f"{host}:!<offline group>"`, because a host name holds no comma.
- The helper's test is `tests/infra/test_plan.py:363:def test_a_host_in_the_offline_group_is_never_in_the_limit(`, whose cases are `all`, `node-5.example.com` and `k3s_agent` and whose assert is `tests/infra/test_plan.py:366:assert host_pattern(limit, offline) == pattern`, so the comma case and the `gpu_nodes` case are new.
- The apply tests plan with the Lab of `tests/commands/test_infra_apply.py:208:def test_the_hosts_with_no_disruptive_class_run_together_with_no_drain(`, where `tests/commands/test_infra_apply.py:712:plan = lab.plan(f"{NODE_4},{NODE_3}")` gives one together host, and `tests/support/infra.py:269:def site_events(project: Path, hosts: Collection[str], run: str = "site") -> list[dict[str, Any]]:` drops the failed task of node-4, so node-4 runs together and node-3 alone.
- The fake reads the limit at `tests/support/infra.py:293:def limit_hosts(call: ProcessCall) -> tuple[str, ...]:` and `tests/support/infra.py:296:return tuple(pattern.split(":", 1)[0].split(","))`, and writes the steps at `tests/support/infra.py:343:steps.append(f"{kind} {','.join(limit_hosts(call))}")`, so a `!` term of a comma pattern would read as a host.
- The plan dry run is `tests/commands/test_infra_plan.py:313:def test_dry_run_starts_no_process(`, which plans `node-3.example.com`, one host with no comma, so `tests/commands/__snapshots__/test_infra_plan.ambr:20:--limit 'node-3.example.com:!<offline group>'` keeps its text.
- The commands of this section name the repo as one token, `example-org/infra`, because the plan and apply commands take the repo and the playbook as two positional arguments.
- No function that the plan calls needs a checkout, a client or a network: `host_pattern` is pure, and each test drives the CLI with `ProcessFake`, `FakeCluster` and the recorded events under `tests/fixtures/infra/runner_events/`.
- The first checks against the real system run on a workstation with a checkout of the infra repo and `ansible-core` under `user-data/tools/`: `uv run devops infra plan example-org/infra ansible/playbooks/02_nvidia.yaml --limit <gpu-node-a>,<gpu-node-b> --dry-run` must show `--limit '<gpu-node-a>,<gpu-node-b>,!offline'`, and then `uv run devops infra apply example-org/infra ansible/playbooks/02_nvidia.yaml --plan <plan-id> --limit <gpu-node-a>,<gpu-node-b>` must reach both hosts, with the `PLAY RECAP` of its `stdout` listing them.
- The verify programs are `uv run devops ci test` with the test path of each group: `uv`, `devops` and `pytest` come from the runner image, and `ansible-core` is `NOT_IN_RUNNER`, so no verify starts Ansible, because `ProcessFake` answers each `ansible-runner run` and `FakeCluster` answers each `kubectl`; the pod sets `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, drops `ALL` capabilities and uses `seccompProfile: RuntimeDefault`, and each test writes only under `tmp_path`.
- `read_issue` for #5455 showed a closed item, released in v0.130.0, that changes the critical-alert gate of the apply and not the host pattern, and the context lists no overlap, no metric sender and no issue dependency, so the plan has no dependency.

## Existing Tool Considered

None: the alternatives check of 2026-11-19 recorded the verdict `none` in the issue body, and the change edits the existing `host_pattern` helper with no new dependency and no new component.

## Dependencies

None.
