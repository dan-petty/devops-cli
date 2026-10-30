# Tasks

## 1. Read scope/security in the urgent-fix rule

- [x] 1.1 In `tests/test_workflow_contracts.py`, name `scope/security` in `_URGENT_LABELS`, assert that `.github/labels.yml` declares it and that the step does not name `type/security`, and verify that `uv run devops ci test tests/test_workflow_contracts.py` fails on the base
- [x] 1.2 In `.github/workflows/release.yml`, read `scope/security` with `priority/p1-high` in the step `Merge the Release Pull Request on an Urgent Fix`, and verify that `uv run devops ci test tests/test_workflow_contracts.py` passes
- [x] 1.3 Name `scope/security` in `RELEASE_CYCLE.md` and ADR 0013, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
