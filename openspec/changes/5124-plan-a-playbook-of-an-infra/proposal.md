# Proposal: #5124 plan a playbook of an infra repo in check mode

## Why

Closes #5124. A change to dan-petty/homelab reaches the hosts by `make <target> ANSIBLE_ARGS="--limit <host>"`. Before the run, nobody sees which tasks change on which host, or that a change restarts k3s. On 2026-11-12 homelab #19 (kubelet memory reservations) was merged and not applied. The owner ran `make k3s ANSIBLE_ARGS="--limit hawk.lan --check --diff"`: ok=9 changed=2, the agent config template with no diff (it holds the join token) and the restart of `k3s-agent`. Only a person who reads the task names sees that the apply restarts k3s. Agents may apply plays, but only after a plan of the same commit (tracker #5120, sections 5 and 6). The plan is the record that the apply of #5125 checks.

## What Changes

- A new command, `devops infra plan <repo> <playbook> [--limit] [--tags] [--ref] [--path] [--format] [--dry-run]`.
- The command exports one commit that `origin` holds with `git archive` (by default the head of the default branch; `--ref` takes a branch of `origin` or `pull/<number>/head`) into the project folder of an ansible-runner private data folder under `<data dir>/infra/<owner>/<name>/plans/` (mode 0700). It never reads the working tree. The shared reader `infra/repo_tree.py` gets `export_commit` and the ref steps.
- It installs the pinned collections of `collections/requirements.yml` once for each version of the file (`<data dir>/infra/collections/<sha256>/`), and runs `ansible-runner run <folder> --playbook <playbook> --limit <limit>:!<offline group>` with `--check --diff -v`, the inventory of the profile, `--tags`, and the key of `devops ssh` as `ansible_ssh_private_key_file`, through `run_subprocess`. The environment sets the repo's `ansible.cfg`, host key checks on, `ANSIBLE_INJECT_INVOCATION`, JSON results and a line for each skipped host. ansible-runner stops the run at its own `job_timeout`, 60 s below the process bound of 1800 s.
- It reads `artifacts/<ident>/job_events/*.json` into Pydantic models. For each host: the changed tasks (name, path from the repo root, action), the changes with the diff hidden (`diff: false`, `no_log`), the unchecked tasks (skipped by check mode, not by a false `when`), the failed tasks, and the disruptive classes `reboot`, `service-restart:<unit>` (a restart, reload or stop of a unit that the host variable `devops_infra_nondisruptive_units` does not list) and `drain`.
- It saves `plan.json` (repo, ref, commit, playbook, limit, host pattern, tags, ansible-core version, inventory hash, status, error, the plan of each host) with the runner artifacts in `plans/<id>/`, and removes the export. The plan id is the SHA-256 of the canonical JSON of the facts, without the time, the runner ident and the folder. A failed task or a run that does not end `successful` marks the plan `failed`, and the command exits 1.
- The output is a table of hosts, a table of tasks and the plan id, or the plan model with `--format json|yaml`.
- An agent needs the agent access level `plan` or above, checked before any process starts (`require_agent_level`). `--dry-run` starts no process and lists the commands.
- New glossary terms in CONTEXT.md: infra plan, disruptive class, unchecked task.

## Capabilities

- `infra-plan` (new): the check-mode run of a playbook, the plan of each host, the plan record and its id, the access level, the output and the dry run.

## Impact

- One new command. No setting changes. New defaults: `DEFAULT_INFRA_PLAN_TIMEOUT_SECONDS` (1800 s), `DEFAULT_INFRA_PLAN_TIMEOUT_MARGIN_SECONDS` (60 s) and `DEFAULT_INFRA_GALAXY_TIMEOUT_SECONDS` (600 s).
- The plan connects to the hosts of the limit in check mode. Check mode changes no host; a task with `check_mode: false` runs for real, and `devops infra onboard` lists each one. On homelab those tasks only read, or run `rsync --dry-run`.
- The plan records stay in the data folder. Nothing removes old plans yet; the apply of #5125 refuses a plan older than `infra.plan_max_age_hours`.
- The change fits one pull request.

## Feasibility

- **ansible-runner 2.4.3 with ansible-core 2.22.0** (the pinned `[python.ansible-core]` tool environment, Python 3.14.10), probed on 2026-11-12 with the probe in `tests/fixtures/infra/runner_events/probe/`:
  - A changed `template` gives `runner_on_ok` with `res.changed` and a `res.diff` list; with `diff: false` the list is empty. A `no_log` result is `{"censored": ...}` with no `changed`, but `playbook_on_stats` counts the change for the host.
  - `runner_on_skipped` has no `res`. At `-v` with `ANSIBLE_CALLBACK_RESULT_FORMAT=json`, its `stdout` is `skipping: [<host>] => {...}`: a check-mode skip of `command` has `"msg": "Command would have run if not in check mode"`, and a false `when` has `false_condition`.
  - A `systemd` task with the templated state `restarted` gives `res.state: started`. With `ANSIBLE_INJECT_INVOCATION=True` (ansible-core 2.21 and later) the result holds `invocation.module_args.state: restarted`, rendered.
  - `ansible.builtin.reboot` in check mode returns `changed` and `rebooted` before it connects. A notified handler runs in check mode and gives `runner_on_ok`.
  - `env/settings` with `job_timeout: 3` stops a 20 s pause after 3 s with exit code 254 and the status file `timeout`.
- **Live run on dan-petty/homelab, 2026-11-12** (origin/main at 19f0457, homelab #19 merged and not applied): `devops infra plan dan-petty/homelab ansible/playbooks/03_k3s.yaml --limit hawk.lan` gave on `hawk.lan` the agent config template changed with the diff hidden and the `systemd` task with `service-restart:k3s-agent`, ok=9 changed=2 in the run recap, the same as the owner's check run, and no other host. A second run gave the same plan id. The `uptime -s` of hawk (08:03:39) and the `k3s-agent` `ActiveEnterTimestamp` (08:03:51, PID 1163, 0 restarts) were the same before and after. The output is in a comment of the pull request.

## Existing Tool Considered

ansible-runner (Apache-2.0, used by AWX and ansible-navigator) gives the private data folder, the AWX job event schema, the artifacts and the job timeout. `ANSIBLE_INJECT_INVOCATION` of ansible-core gives the rendered arguments. The command adds the export, the event classification and the record: about 3.5M tokens to build, 0.5M tokens a quarter to keep and fix, and 5 hours, as #5124 estimated. The same on the `ansible.posix.jsonl` callback costs about 1.5M tokens and 3 hours more, because devops would build the run folder, the timeouts and the event model. The change deletes no internal code: `default_branch_tree` now calls the new `export_commit`.
