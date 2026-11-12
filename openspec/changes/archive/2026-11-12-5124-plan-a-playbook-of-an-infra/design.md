# Design

## Decisions

- **The plan folder is the private data folder.** The export of the commit goes to `<folder>/project`, so ansible-runner starts `ansible-playbook` there and the repo's `ansible.cfg` applies, as for a person who runs the play in the repo. The run folder is a new `mkdtemp` folder under `plans/` (mode 0700), and it moves to `plans/<id>/` after the run, because the id is known only from the result. The export is removed after the run; the commit gives it again.
- **The facts come from the job events, not from the repo's YAML.** The events name the action that ran (`resolved_action`), the task path, the result and, with `ANSIBLE_INJECT_INVOCATION`, the rendered arguments. A templated state, such as homelab's `"{{ 'restarted' if ... else 'started' }}"`, is read as Ansible rendered it.
- **The safe side for each unknown.** A service result with no arguments is disruptive. A `no_log` result counts as a change with the diff hidden when the stats of the host count more changes than the other results show. A skip whose result does not read is unchecked. A templated `devops_infra_nondisruptive_units` lists no unit.
- **A false `when` is not unchecked.** Most skips in homelab come from a `when` on a fact that a read gave, such as the k3s install script when the binary exists. Listing them as unchecked would make every plan look unsafe. The skip result at `-v` names `false_condition` for such a skip.
- **The id covers the facts.** `PlanContent` holds the facts; `InfraPlan` adds the id, the time, the runner ident and the folder. The id is the SHA-256 of the sorted, compact JSON of `PlanContent`, so the same events at the same commit, limit and tags give the same id, and the apply can compute it again from the record.
- **Collections once for each version.** The install goes into a staging folder and moves to `<data dir>/infra/collections/<sha256 of requirements.yml>/` after it succeeds, so a failed install leaves no half folder and a second plan starts no Galaxy download.
- **Nested bounds.** ansible-runner's `job_timeout` (1740 s) ends before the process bound (1800 s), so a slow run ends with its artifacts and the status `timeout`, and the plan names the cause.
- **The access check comes first.** `plan_entry` checks the level after the repo name is known and before the export, so an agent on a repo at `none` starts no process.

## Rejected alternatives

- **A skip list by module (`command`, `shell`, `script`, `raw`).** A module that does not support check mode at all also skips, and a `command` with a false `when` is not unchecked. The probe showed that the skip result tells the two apart.
- **`res.state` and `res.status.ActiveState` of the systemd result.** The probe showed `state: started` for a restart, so a restart and a start of a running unit read the same. The rendered arguments name the state.
- **`ANSIBLE_DISPLAY_ARGS_TO_STDOUT` and `task_args`.** They hold the raw arguments, so a templated state stays a template.
- **Keep the export in the plan folder.** The commit gives the same files, and the export of a repo can hold large files.
- **One plan folder for each run with a random name.** The apply looks up a plan by its id, so the folder name is the id.
