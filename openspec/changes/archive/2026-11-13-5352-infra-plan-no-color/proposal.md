# Proposal: #5352

## Why

`devops infra apply` stops at the fresh check when the plan came from a run with no terminal and the apply runs in a color terminal (#5352). ansible-runner starts `ansible-playbook` in a pseudo-terminal, and the process runner passes `TERM` and `COLORTERM` from the caller. Thus with `TERM=xterm-256color` the default callback puts color codes around the text of each event. The plan reads the skip result after ` => ` in the event `stdout` as JSON. A result in color does not read, so the plan counts the skip as unchecked (the safe side). A skip by a false `when` is then unchecked in a color terminal and not unchecked with no terminal, and the fresh check differs from the plan. Closes #5352.

## What Changes

- Every `ansible-runner` run of a playbook (the plan, the fresh check and the run of an apply) gets `ANSIBLE_NOCOLOR=True` and `ANSIBLE_FORCE_COLOR=False` in its environment. `ANSIBLE_FORCE_COLOR=False` replaces a `force_color` of the repo's `ansible.cfg`, as `ANSIBLE_CALLBACK_RESULT_FORMAT` replaces its `result_format`. The callback then writes the same event text in a color terminal and with no terminal, and the plan of a host is the same in both.
- A skip result that does not read as JSON stays unchecked, as before.
- The change is observable: the plan of a host in a color terminal changes, and `devops infra apply` passes the fresh check that stopped it. Thus it carries a delta of the capability `infra-plan`.

## Capabilities

- `infra-plan`: ADDED requirement "The run output has no color".

## Impact

- Code: `src/devops_cli/infra/plan.py` (`_PLAN_ENV` and its comment, the docstrings of the module and of `runner_env`).
- Tests: `tests/infra/test_plan.py`, `tests/commands/test_infra_plan.py`, `tests/commands/test_infra_apply.py`, `tests/support/infra.py`, and the new recorded run `tests/fixtures/infra/runner_events/site_color.jsonl`.
- A plan record made in a color terminal before this change can show more unchecked tasks than a fresh check after it. Such a plan stops at the fresh check. Make the plan again.
- No setting, command, option or message changes. No manifest changes. The change fits one pull request.

## Feasibility

The premise was confirmed against `origin/main` and the pinned tools (ansible-core 2.22.0, ansible-runner 2.4.3 in the tool environment of `[python.ansible-core]`):

- `_is_check_mode_skip` (`src/devops_cli/infra/plan.py`) returns `True` when `json.loads` of the text after ` => ` fails. `_PLAN_ENV` holds no `ANSIBLE_NOCOLOR`.
- `DEFAULT_ALLOWED_ENV_VARS` (`src/devops_cli/core/process.py`) holds `TERM` and `COLORTERM`, and no allowed name or prefix matches `ANSIBLE_NOCOLOR`. Thus a caller `ANSIBLE_NOCOLOR=1` does not reach the run, as the comment of the owner on the issue says.
- `ansible_runner/runner.py` starts the command with `pexpect`, which gives it a pseudo-terminal. `ansible_runner/display_callback/callback/awx_display.py` (`v2_runner_on_skipped`) puts no result in the event data of a skip, so the event `stdout` is the only source of the skip result.
- `ansible/utils/color.py` turns color off when `ANSIBLE_NOCOLOR` is true. Else it turns color on when `stdout` is a terminal and `curses.setupterm()` finds a terminal with colors. `ANSIBLE_NOCOLOR` is the setting `nocolor` of `ansible.cfg`, also read from `NO_COLOR` (`ansible/config/base.yml`).
- Three check-mode runs of the probe `tests/fixtures/infra/runner_events/probe/` on all hosts, as `tests/support/infra.py` says:
  - With no `TERM`: 0 of 65 events hold an escape code. node-1 has 1 unchecked task and node-3 has none.
  - With `TERM=xterm-256color`: 21 events hold escape codes, and a skip has the `stdout` `\x1b[0;36mskipping: [node-3.example.com] => {"changed": false, "false_condition": ...}\x1b[0m`. node-1 has 2 unchecked tasks (`Remove the old demo unit` too) and node-3 has 1 (`Download and execute K3s agent installation script`).
  - With `TERM=xterm-256color` and `ANSIBLE_NOCOLOR=True`: 0 events hold an escape code, and the plan of each host is equal to the plan of the run with no `TERM`.
- `ansible/utils/color.py` applies `ANSIBLE_FORCE_COLOR` after `ANSIBLE_NOCOLOR`, and `force_color` turns color on also with no terminal. An environment variable replaces the same setting of `ansible.cfg`: with `force_color = True` in `ansible.cfg` and `ANSIBLE_FORCE_COLOR=False` in the environment, `ansible-config dump --only-changed` shows `ANSIBLE_FORCE_COLOR(env: ANSIBLE_FORCE_COLOR) = False`. A check-mode run of a playbook with one skip by a false `when`, with `TERM=xterm-256color` and that `ansible.cfg`, gives the skip `stdout` `\x1b[0;36mskipping: [localhost] => {"false_condition": false}\x1b[0m` with `ANSIBLE_NOCOLOR=True` only, and `skipping: [localhost] => {"false_condition": false}` with `ANSIBLE_FORCE_COLOR=False` too.

## Existing Tool Considered

Ansible has the setting `ANSIBLE_NOCOLOR` (`nocolor` in `ansible.cfg`). The change sets it and adds no new tool or library. It deletes no internal code.
