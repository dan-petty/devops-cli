# Tasks

## 1. Turn off the color of every run of a playbook

Kind: behavior. Reads: `src/devops_cli/infra/plan.py`, `src/devops_cli/core/process.py`, `tests/support/infra.py`. Changes: `src/devops_cli/infra/plan.py`, `tests/support/infra.py`, `tests/fixtures/infra/runner_events/site_color.jsonl`, `tests/commands/test_infra_plan.py`, `tests/commands/test_infra_apply.py`, `tests/infra/test_plan.py`.

- [x] 1.1 Record the run `site` of the probe again with `TERM=xterm-256color` and no `ANSIBLE_NOCOLOR` as `tests/fixtures/infra/runner_events/site_color.jsonl`, and say how in `tests/support/infra.py`. Add `terminal_events` to `tests/support/infra.py`: it answers a run with the recording `site_color` when the environment of the run is the environment of that recording, else with the recording `site`. Add `ANSIBLE_NOCOLOR=True` to the environment that `test_the_run_is_check_mode_on_the_limit_without_offline_hosts_with_the_key` expects
  - Verification: `$ uv run devops ci test tests/commands/test_infra_plan.py` fails on the base
- [x] 1.2 Add `test_a_plan_with_no_terminal_passes_the_fresh_check_of_its_apply_in_a_color_terminal` to `tests/commands/test_infra_apply.py`: the plan of node-3 runs with no `TERM`, the apply runs with `TERM=xterm-256color`, the apply exits 0 with each step of node-3, and each `ansible-runner` run gets `ANSIBLE_NOCOLOR=True`
  - Verification: `$ uv run devops ci test tests/commands/test_infra_apply.py` fails on the base
- [x] 1.3 Add `test_a_skip_result_in_color_stays_unchecked` to `tests/infra/test_plan.py`: in the recording `site_color`, the two skips by a false `when` are unchecked, and the rest of each host plan equals the plan of the recording `site`
  - Verification: `$ uv run devops ci test tests/infra/test_plan.py` passes on the base and after the change
- [x] 1.4 Add `ANSIBLE_NOCOLOR=True` to `_PLAN_ENV` in `src/devops_cli/infra/plan.py`, and say why in the docstrings of the module and of `runner_env`
  - Verification: `$ uv run devops ci test tests/commands/test_infra_plan.py tests/commands/test_infra_apply.py tests/infra/test_plan.py` passes

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
