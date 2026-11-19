# Tasks

## 1. Fix the offline separator of host_pattern

Kind: behavior. Reads: `src/devops_cli/infra/plan.py`, `tests/infra/test_plan.py`, `tests/commands/test_infra_plan.py`, `tests/commands/test_infra_apply.py`, `tests/infra/test_apply.py`. Changes: `src/devops_cli/infra/plan.py`, `tests/infra/test_plan.py`.

- [x] 1.1 Add `pytest.param("a,b", "offline", "a,b,!offline", id="comma-limit")` and `pytest.param("gpu_nodes", "offline", "gpu_nodes:!offline", id="single-group")` to `test_a_host_in_the_offline_group_is_never_in_the_limit` in `tests/infra/test_plan.py`; the comma case fails on main, where `host_pattern` gives `a,b:!offline`
  - Verification: `$ uv run devops ci test tests/infra/test_plan.py` fails on the base
- [x] 1.2 Change `host_pattern` in `src/devops_cli/infra/plan.py` so it joins the offline exclusion with a comma when the limit holds a comma and with a colon when it holds none. Keep `all:!offline` when the limit is absent, and keep the pattern unchanged when no offline group is named. Update the module docstring line that shows the limit as `<limit>:!<offline group>`. The cases `all`, `node-5.example.com` and `k3s_agent` of `tests/infra/test_plan.py` keep their answer
  - Verification: `$ uv run devops ci test tests/infra/test_plan.py` passes

## 2. Show the fixed separator in the dry run of the plan command

Kind: behavior. Reads: `src/devops_cli/infra/infra_plans.py`, `src/devops_cli/infra/plan.py`, `tests/commands/test_infra_plan.py`. Changes: `src/devops_cli/infra/infra_plans.py`, `tests/commands/test_infra_plan.py`.

- [x] 2.1 Add `test_the_dry_run_shows_each_term_of_a_comma_limit` to `tests/commands/test_infra_plan.py`: a dry run with `--limit node-1.example.com,node-2.example.com` shows `--limit 'node-1.example.com,node-2.example.com,!<offline group>'` and starts no process. It fails on main, which shows the colon before the exclusion
  - Verification: `$ uv run devops ci test tests/commands/test_infra_plan.py` fails on the base
- [x] 2.2 Build the shown pattern of `plan_plan` in `src/devops_cli/infra/infra_plans.py` with `host_pattern(limit, "<offline group>")` instead of the literal `:!<offline group>`, and import `host_pattern` from `devops_cli.infra.plan`. Keep the snapshot of the one-host limit unchanged
  - Verification: `$ uv run devops ci test tests/commands/test_infra_plan.py` passes

## 3. Show the fixed separator in the dry run of the apply command

Kind: behavior. Reads: `src/devops_cli/infra/infra_plans.py`, `src/devops_cli/infra/plan.py`, `tests/commands/test_infra_apply.py`. Changes: `src/devops_cli/infra/infra_plans.py`, `tests/commands/test_infra_apply.py`.

- [x] 3.1 Add `test_the_dry_run_shows_each_together_host_as_its_own_term` to `tests/commands/test_infra_apply.py`: plan the hosts `node-1.example.com` and `node-4.example.com` with the event of the task `Restart the demo unit` dropped, then run the apply with `--dry-run` and assert that the shown request holds `--limit 'node-1.example.com,node-4.example.com,!<offline group>'`. It fails on main, which shows the colon before the exclusion
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py` fails on the base
- [x] 3.2 Build the shown pattern of the together run in `plan_apply` in `src/devops_cli/infra/infra_plans.py` with `host_pattern(",".join(together), "<offline group>")` instead of the literal `:!<offline group>`. Keep the snapshot of the one-host together run unchanged
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py` passes

## 4. Read the hosts of a comma limit in the fake runner

Kind: other. Reads: `tests/commands/test_infra_apply.py`, `tests/support/infra.py`, `src/devops_cli/infra/apply.py`. Changes: `tests/commands/test_infra_apply.py`, `tests/support/infra.py`.

- [ ] 4.1 Drop each term of the `--limit` that starts with `!` in `limit_hosts` in `tests/support/infra.py`, so the fake reads the hosts of the comma form. Add `test_the_together_run_names_each_host_as_its_own_term` to `tests/commands/test_infra_apply.py`: plan `node-1.example.com` and `node-4.example.com` with the event of the task `Restart the demo unit` dropped, apply the plan, and assert that the `--limit` of the `ansible-runner` call is `node-1.example.com,node-4.example.com,!offline` and that the first step is `run node-1.example.com,node-4.example.com`
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py` passes

## Criteria

- Group 1: A test of `host_pattern("a,b", "offline")` gives a pattern in which `a`, `b` and `!offline` are each one term. It fails on `main` (`devops ci fail-to-pass`).
- Group 1: A test of `host_pattern("gpu_nodes", "offline")` keeps a pattern that excludes the offline group.
- Group 4: An apply test with a fake runner: a run together of 2 or more hosts gets a limit in which each host is one term.
- Group 3: The dry-run text of `infra_plans.py` shows the new pattern.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
