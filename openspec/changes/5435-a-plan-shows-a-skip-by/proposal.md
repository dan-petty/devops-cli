# Proposal: #5435

## Why

`devops infra plan` shows a skip by a false `when` as "no change" and every other skip as unchecked. Some tasks cannot run in check mode while the change of an earlier task is still to come: apt cannot find a package in a source that check mode did not add, and containerd lists a runtime only after the restart. A role skips such a task with a `when` that names `ansible_check_mode`. The skip result then has `false_condition`, so the plan shows the task neither as changed nor as unchecked. `devops infra apply` runs the playbook, the task changes, and guard 7 (`unplanned_changes`) stops the apply after the run changed the host. On a disruptive host, the drained node stays cordoned. The gVisor play of the infra repository has this problem on its first apply and on each change of its pin. An agent at level `safe` can also apply such a plan, because the plan shows no unchecked task.

## What Changes

- `src/devops_cli/infra/plan.py`: a skip by a false `when` item that names `ansible_check_mode` is unchecked, for a task and for a loop item. The plan reads the names of the item with the parser of Jinja2, and it renders nothing. A `when` item that does not parse is unchecked: the safe side.
- The probe of the recorded runs gets the play `ansible/playbooks/check_when.yaml` and the host node-5. The new recorded run `check_when.jsonl` holds a task and a loop item that a `when` with `ansible_check_mode` skips, and a task whose first false `when` item does not name check mode.
- `tests/infra/test_plan.py` pins the plan of node-5.
- The module docstring of `plan.py`, the docstring of `tests/support/infra.py` and the spec `infra-plan` give the rule.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `infra-plan`: a skip by a false `when` that names `ansible_check_mode` is unchecked.

## Impact

- Code: `src/devops_cli/infra/plan.py`
- Tests: `tests/infra/test_plan.py`, `tests/support/infra.py`, the probe and the recorded run `check_when.jsonl` under `tests/fixtures/infra/runner_events/`
- Behavior: a plan of a playbook with such a `when` shows more unchecked tasks. Such a plan needs the agent level `full`, and its apply accepts the changes of those tasks. A plan of a playbook with no such `when` does not change.

## Feasibility

- ansible-core 2.22.0, the pin of `src/devops_cli/tools_lock/ansible-core.in`: `Task._resolve_conditional_with_item` in `ansible/playbook/task.py` returns the first `when` item that is false, and `UnifiedTaskResult.record_conditional_false` in `ansible/_internal/_task.py` writes it as `false_condition`. So a `when` list `[work_due, not ansible_check_mode]` names check mode only when the work is due.
- The recorded run of the pinned `ansible-runner` 2.4.3 on the probe: the task skip prints `"false_condition": "not (ansible_check_mode and demo_source is changed)"` after `=> `, and the skipped loop item has `false_condition` and `skip_reason`, but no `skipped` key, in the `results` of a `runner_on_ok` event.
- `jinja2.Environment.parse` gives the syntax tree of a condition without the tests and filters of Ansible (`is changed`). `jinja2.meta.find_undeclared_variables` compiles the tree and fails on an unknown test, so the plan walks the `Name` nodes of the tree.
- `src/devops_cli/infra/apply.py`: `unplanned_changes` accepts a change of a task that the plan shows as unchecked, and `access.py` asks for the level `full` for a plan with an unchecked task.

## Existing Tool Considered

ansible-core writes the false `when` item into each skip result, and Jinja2 (`jinja2==3.1.6`, already a dependency) parses it. The change adds no tool and no hand-written parser.
