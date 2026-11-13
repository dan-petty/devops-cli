# Design

## Decisions

- **A guideline, decisions and generated facts.** The guideline holds what applies with no change to each managed project. The README of the environment tree holds the decisions of one cluster. A dashboard, a command or the project review report gives each measured value, and no document copies it. So no agent updates a measured value by hand.
- **One guideline for the resources.** The SRE guideline owns the SLOs, alerts, incidents and dashboards. The agentic jobs guideline owns the attempt, token and time limits of a job. This guideline owns CPU, memory, process IDs, disk, image pulls, runtimes, probes, batch Jobs and placement. The guideline links the other guidelines through the index, because they are not in the folder yet.
- **A measure for each target.** Each target names its kubernetes-mixin alert, node-mixin alert, KRR report, kube-linter check or metric. A target of one cluster, such as the pod start and the runner start, is a decision of `k8s/README.md`.
- **Gaps in a tracker.** Tracker #5542 holds the gaps of the first draft. `k8s/README.md` links it and holds no gap row, so an issue that closes changes no document.
- **A test of the rule.** `tests/invariants/test_guidelines.py` refuses an issue number, a date, an environment tree path, a node placeholder, `today`, `currently` and a state or query row id in each file of `docs/guidelines/`. It also fails when the index has no line for a guideline. A guideline that holds none of these facts can apply to each managed project.
- **New ids.** The guideline numbers its targets T1 to T10 and its rules R1 to R8. The first draft was never merged, so no document keeps its ids, and `docs/guidelines/sre.md` links the targets by name.
- **Batch Jobs.** The owner asked that jobs run asynchronously and be ready for event-driven triggers. The guideline holds the Kubernetes part: a Job that an event or a schedule starts, a service that does not wait, a Job name from the event id, and the bounds of each Job.

## Rejected alternatives

- **Keep the measured state with a date for each row.** The owner directions of 2026-11-13 replace it: a measured row in git goes stale, and an agent must update it by hand.
- **A short profile of the cluster in `docs/`.** The environment decisions move with the environment tree to the infra repo, so they go in `k8s/README.md` now.
- **A gap table in the README.** The owner chose tracker issues. An issue that closes as a duplicate or as not planned makes a row stale with no pull request.
- **The AGENTS.md row in this change.** #5536 adds the route to the guideline index in the template and in AGENTS.md together.
- **A spec delta.** `openspec/config.yaml` gives a documentation change no delta. The change alters no command, option, message or manifest.
