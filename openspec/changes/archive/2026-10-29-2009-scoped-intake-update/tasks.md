# Tasks

## 1. Scoped intake of one issue

- [x] Add failing tests: the scoped-update table; an `issues` delivery of each action intakes only its issue and writes no last success; an edit of an Item and an event with no scoped update change nothing; a poll after a scoped update decides a lost `opened` or `reopened` delivery and not the handled one; a scoped update keeps the record that a capped round left
  - Verification: `uv run devops ci test tests/test_roadmap_run.py`
- [x] Add `IntakePlan.others_fresh` and `IntakeRecord.merged` to `roadmap/intake.py`, and `WebhookDelivery`, `ScopedUpdate`, `SCOPED_UPDATES` and `run_scoped_update` to `roadmap/run.py`
  - Verification: `uv run devops ci test tests/test_roadmap_run.py tests/test_roadmap_intake.py`
- [x] Write ADR 0017 and point ADR 0003 to it, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2009-scoped-intake-update`

## Workflow follow-up

- The second part of #1533: the roadmap consumer of ADR 0009 gives each subscribed event to `run_scoped_update` on the model lane, `GitHubWebhookPayload` reads the issue number, and AGENTS.md and `k8s/README.md` describe the event-driven flow.
- Pending a person: once the Service runs again, a real delivery of each subscribed event runs its scoped update and no whole round.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
