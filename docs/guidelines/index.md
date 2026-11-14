# Guidelines

A guideline is a rule or a method that applies with no change to each managed project. The docs site publishes each guideline, and no managed repository holds a copy. A guideline names no issue, date, node or path of one environment. The README of the environment tree of a project holds the decisions of its environment, and a tracker issue holds its gaps. The test `tests/invariants/test_guidelines.py` holds each guideline to these rules, and it fails when a guideline of this folder has no line below.

- [Agentic jobs](agentic-jobs.md) — The default targets of an agentic job, the job model, the measure of a job, the tuning loop, and the rules for agents and jobs.
- [Production readiness](production-readiness.md) — The checklist of a service and a repository, the check of each row, the readiness review and the steps of a new service.
- [SRE](sre.md) — The service catalog, the SLOs, the alerts, the incidents, the change safety, the backups, the capacity and the runbooks of a service.
