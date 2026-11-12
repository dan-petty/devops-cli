# Proposal: #5125 apply a saved plan one node at a time

## Why

Closes #5125. The owner decided on 2026-11-12 that agents apply plays on the hosts of an infra repo ("Agents apply all"), and that the agent access level is a setting of each infra repo, with dan-petty/homelab at `full`. Today AGENTS.md says that only a person changes hosts, so an agent gives the owner `make` commands, for example `make k3s ANSIBLE_ARGS="--limit hawk.lan"` for dan-petty/homelab#19, which restarts k3s on the host. The auto-mode classifier refused that command from an agent. Agents need one sanctioned path that applies a reviewed plan (#5124) with guards, one node at a time (tracker #5120, sections 4, 7 and 11).

## What Changes

- A new command, `devops infra apply <repo> <playbook> --plan <id> [--limit] [--tags] [--path] [--auto-approve] [--format] [--dry-run]`. The caller gives the playbook, limit and tags of the plan again, and the apply refuses a plan with others.
- **Access level.** An agent needs `safe` for a plan with no disruptive class and no unchecked task, else `full` (`apply_level` in `infra/access.py`). A person may apply every plan.
- **Guards for every caller.** The plan record exists, its facts give its id again, it ended `ok`, and it is not older than `infra.plan_max_age_hours`. `origin` holds the commit (`git merge-base --is-ancestor` after a fetch). An agent applies only a commit of the default branch, or at `full` the head of an open pull request of the infra repo (`get_pull_status`). An agent apply is refused when the config or the inventory of the commit turns host key checks off. Every node of the kube context, except the nodes of the hosts out of service, is Ready with no memory, disk or PID pressure, and no `severity="critical"` alert fires when `prometheus.url` is set.
- **Steps.** The apply exports the commit of the plan into `plans/<id>/applies/<apply id>/project` and removes it after. The hosts with no disruptive class run together in one run. Each disruptive host runs alone in plan order: read the node, `kubectl drain --dry-run=server` (the drain check), `kubectl drain --ignore-daemonsets --delete-emptydir-data` with no `--force`, a fresh check-mode run of the host that must equal its plan, the run (`-v`, no `--check`, no `--diff`), wait for Ready and the GPUs of before, the health gate again, and `kubectl uncordon` only when the node was schedulable before. The waits read again through a gap of the API server.
- **Stops.** A task that changed in the run and that the plan does not show as changed or unchecked, a failed task, and each failed step stop the apply. The node stays as the step left it, cordoned after a drain, the hosts after it do not run, and the command exits 1 with the host, the step and the reason.
- **Audit and telemetry.** Each apply that passes the argument checks writes one audit record `infra.apply` with the result `ok`, `refused` or `stopped`, the caller and its tool, the level, the repo, the commit, the ref, the plan id, the playbook, the limit, the tags, the reason, and each host with its node, disruptive classes, outcome, step, reason and runner idents. A new counter, `devops_cli_infra_runs_total{repo,command,result}`.
- Without `--auto-approve`, the command asks a person before any process starts. `--dry-run` starts no process and lists the commands in order, with the hosts of the plan record when it reads.
- **Policy text.** SECURITY.md gets the section `## Infra Repos` in the words of design section 11, and item 3 lists `ansible-runner`. The design text for the "Only a person" paragraph of AGENTS.md does not fit the cap of 6,500 characters; see Impact.
- New glossary terms in CONTEXT.md: infra apply, fresh check, drain check.
- `infra/plan.py` gets `Playbook.run`, which the plan and the apply share, and `runner_argv(check=False)`. `infra/repo_tree.py` gets `origin_holds` and `export_tree`. `infra/status.py` makes `gpu_total` and `memory_bytes` public for the node reads of `infra/nodes.py`.

## Capabilities

- `infra-apply` (new): the access level of an apply, the plan and commit guards, the host key and health gates, the steps of each host, the stops, the audit record, the confirmation and the dry run.

## Impact

- One new command and one new counter. No setting changes; the apply reads `infra.plan_max_age_hours`, `infra.drain_timeout_seconds` and `infra.node_ready_timeout_seconds` of #5121. New defaults for the kubectl request bound (30 s), the kubectl process bound (60 s), the drain check (30 s), the drain margin (60 s) and the poll interval (10 s). A new error code, `INFRA_APPLY_REFUSED`.
- The apply changes hosts. A disruptive host is drained, so its pods move to other nodes for the time of the run.
- AGENTS.md: the design text of section 11 makes the file 6,812 characters, and a one-clause form ("hardware; agents change hosts only with `devops infra`") 6,545. The cap is 6,500 and the file had 6,496. The pull request changes "hosts" to "hardware" in the "Only a person" paragraph (6,499 characters). The rule that an agent changes a host only with `devops infra`, the levels and the homelab level are in SECURITY.md `## Infra Repos` and in the help of `devops infra apply`. The owner decides whether other text of AGENTS.md gets shorter to make room.
- The change fits one pull request.

## Feasibility

- **The drain check.** `kubectl drain <node> --dry-run=server --ignore-daemonsets --delete-emptydir-data --timeout=20s` on the homelab cluster (k3s v1.37.2+k3s1), 2026-11-12: the API server checked each eviction and changed nothing (the node stayed schedulable). On the control-plane node it ended with `error when evicting pods/"llm-gateway-db-1" -n "llm": global timeout reached: 20s` and the same for `mattermost-db-1`: two CloudNativePG clusters with 1 instance each, whose primary PodDisruptionBudget allows 0 disruptions. On the 3 agent nodes it ended `drained (server dry run)`. So a real drain of the control-plane node would cordon it, evict its other pods and then stop at the drain bound; the drain check stops the apply before the cordon.
- **The health gate.** `ALERTS{alertstate="firing",severity="critical"}` through the Prometheus client of devops (`devops prometheus query`) answered with no series on 2026-11-12.
- **The run.** The run uses the same `ansible-runner` command line as the plan of #5124 without `--check` and `--diff`; the job events have the same shape, so `host_plans` reads them. The plan of #5124 on dan-petty/homelab showed `service-restart:k3s-agent` on hawk for homelab #19.
- **The pull request head.** `get_pull_status` of the GitHub client gives `state` and `head.sha` of a pull request.
- **The live acceptance run** on dan-petty/homelab at level `full` by an agent is in a comment of the pull request, with each audit record and a table of each node before and after.

## Existing Tool Considered

ansible-runner runs the plays; `kubectl drain`, `kubectl uncordon` and `kubectl get` do the node steps; the Prometheus client of devops reads the alerts; `record_audit_event` writes the record; `detect_agent` names the caller. Considered and not chosen: kured (reboots only, with no plan), AWX and Semaphore (a second control plane and a second secret store). The command adds the guards and the order of the steps: about 4.5M tokens to build, 0.6M tokens a quarter to keep and fix, and 6 hours, as #5125 estimated. The change deletes no internal code: the plan run moves into `Playbook.run`, which both commands call.
