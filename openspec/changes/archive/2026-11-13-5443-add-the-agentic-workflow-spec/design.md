# Design

## Decisions

- **A guideline, decisions and generated facts.** The guideline holds what applies with no change to each managed project. `docs/ROADMAP_WORKFLOW.md` holds the decisions of devops-cli, because it already owns the roadmap jobs and `AGENTS.md` routes to it. `docs/roadmap/job-success.md` keeps the product contract of the result line and the grade table. A command, a dashboard or the project review gives each measured value, and no document copies it. So no agent updates a measured value by hand.
- **One guideline for the jobs.** The SRE guideline owns the SLOs, the error budgets and the incident triggers. The Kubernetes guideline owns the resources of a pod, the sizing formula and the batch Job rules. This guideline owns the attempts, the limits, the model, the context, the tools and the evaluation of a job. The tune-down step of the guideline sizes the attempt limits and names the Kubernetes guideline for the memory and the CPU of a pod. The guidelines name each other by name, and the index links each one, because the other guidelines are not on `main` yet.
- **The method moves, the contract stays.** The 80% rule, the ratio `p`, the Wilson interval, the efficiency and the LogQL form of the ratio apply to any job, so they move to the guideline. The result line, the attempt and the intended result of each job, the grade table and the first-pass, window, version and class bullets describe devops-cli, so they stay in `job-success.md` until #5534 generates them. The heading "The 80% rule" of `job-success.md` stays as a link, because the dashboard panels name that page.
- **Asynchronous and event-driven jobs.** The owner asked that the jobs run asynchronously and be ready for event-driven triggers. The guideline gives the job part (P10 and AW-J7): an event or a schedule starts a job, no caller waits, a reconcile pass finds a lost event, the input comes from the record, a unit name from the input stops a second run, and a job starts no job. The Kubernetes guideline gives the Job part. ADR 0021 section 2 is the devops-cli decision that applies them.
- **New rule ids for safety.** The guideline test refuses a state row id `S<n>`, and `AW-S1` holds `S1`. So the safety rules are `AW-G1` to `AW-G4` (guard). The first draft was never merged, so no document keeps the old ids.
- **One-line rules.** A rule of the first draft that only pointed to its owner document now has one line of rule text, so that a managed project can apply it. The owner map in `docs/ROADMAP_WORKFLOW.md` names the document or the code of devops-cli that applies each rule.
- **Gaps in a tracker.** Tracker #5543 holds the gaps of the first draft. `docs/ROADMAP_WORKFLOW.md` links it and holds no gap row, so an issue that closes changes no document.
- **The index and the test with this change.** PR #5492 adds the guideline index, the Guidelines tab and the guideline test, and it is not merged. This change adds the same files, so that its own checks run on the guideline. The tab and the test are the same bytes, so the second merge keeps one copy. The index differs by one line, so the second pull request to merge rebases and keeps both lines.
- **The index within two links of `AGENTS.md`.** `docs/ROADMAP_WORKFLOW.md` links the index, so the two-link test of `tests/invariants/test_agents_md.py` passes with no term in `CONTEXT.md`.

## Rejected alternatives

- **Keep the measured baseline with a date.** The owner directions of 2026-11-13 replace it: a measured table in git goes stale, and an agent must update it by hand.
- **A short profile in `docs/AGENTIC_WORKFLOWS.md`.** The roadmap jobs already have two owner documents. A third breaks "each rule lives in one document only".
- **A gap table in `docs/ROADMAP_WORKFLOW.md`.** The owner chose tracker issues. #5474 and #3109 closed with no pull request on the day of the first draft, and four rows went stale at once.
- **A test change that allows `AW-S1`.** The test is the same file as in PR #5492. A change here makes the two copies conflict, and new ids cost less.
- **Stack this change on PR #5492.** A stacked pull request that touches the same files conflicts either way.
- **A spec delta.** `openspec/config.yaml` gives a documentation change no delta. The change alters no command, option, message or manifest.
