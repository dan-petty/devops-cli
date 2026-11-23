# infra-plan

## MODIFIED Requirements

### Requirement: Hidden diffs and unchecked tasks
A change SHALL have its diff hidden when its result holds an empty diff (`diff: false`) or is censored (`no_log`). A `no_log` result SHALL count as a change only when host stats count more changes than shown. A skipped task or item SHALL be unchecked, except when its skip result names a false `when` item (`false_condition`) or a false condition `skip_reason` that does not name `ansible_check_mode`.

#### Scenario: Changes, skips and a handler
- **WHEN** the recorded run of node-1 changes a template with a diff, a copy with `diff: false` and a `no_log` copy that the stats count, skips a `command` in check mode and a `command` with a false `when`, and runs the notified restart handler
- **THEN** node-1 has four changes, the copy and the `no_log` copy with the diff hidden, one unchecked `command`, and the disruptive class `service-restart:demo`

#### Scenario: A skip by a when that names check mode
- **WHEN** the recorded run of node-5 changes a copy, skips a `command` by `when: not (ansible_check_mode and demo_source is changed)`, skips one item of a loop by a `when` that names `ansible_check_mode`, and skips a `command` whose first false `when` item is `demo_restart_due | default(false)`
- **THEN** node-5 has one change, and the `command` and the loop are unchecked, but the last `command` is not

#### Scenario: Meta end_host skip event
- **WHEN** A test passes to `host_plans` a `runner_on_skipped` event for host `node1.example.com`. Its `stdout` holds `skipping: [node1.example.com] => {"skip_reason": "end_host conditional evaluated to False, continuing execution for node1.example.com"}` and no `false_condition`.
- **THEN** The host plan of `node1.example.com` holds no unchecked task.

#### Scenario: The second callback line
- **WHEN** A test passes to `host_plans` a `runner_on_skipped` event whose `stdout` holds `skipping: [node1.example.com] => {"changed": false, "skip_reason": "Conditional result was False", "skipped": true}`.
- **THEN** The host plan of `node1.example.com` holds no unchecked task.
