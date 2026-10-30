# Tasks

## 1. A stop is not a failed round

- [x] 1.1 Add failing tests in `tests/test_service_limits.py`: the budget raises `ServiceStoppingError` when closed; three rounds that a stop ends leave the count and the row runs the normal round that follows (the sequence of the issue); a stop in the cause chain and in a group; a stop between two real failures; the suspension line names the causes; the ledger file reads with the type of the running version, and a record in the old format loads. Add a test in `tests/test_roadmap_stage_apply.py` that a write meeting the stop error ends the job with it
  - Verification: `uv run devops ci test tests/test_service_limits.py` fails on the base
- [x] 1.2 Add `ServiceStoppingError` to `exceptions/roadmap.py` and `exceptions/__init__.py`; raise it in `RequestBudget.admit`; add `ended_by_stop` and the causes to `FailureLedger` and `_execute_due_rows` in `roadmap/run.py`; let the stage job pass the error in `_write_each`; add the `{causes}` field to `MESSAGES.serve.job_suspended`
  - Verification: `uv run devops ci test tests/test_service_limits.py` and `uv run devops ci test tests/test_roadmap_stage_apply.py`
- [x] 1.3 Run `uv run ruff check`, `uv run ruff format --check` and `uv run mypy --strict` on the changed files
  - Verification: `uv run devops ci lint`

## 2. Documentation

- [x] 2.1 Say in `k8s/README.md` that a round which the stop ends does not count toward the suspension of a row, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Item will not do: a comment by a person on an item of a suspended row does not start the row again. Follow-up issue #2754.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
