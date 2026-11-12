# Tasks

## 1. Record each usage error (behavior)

- [x] 1.1 Write failing tests: one ledger line for each kind, `<value>` for a token, a number and a path, no argument value in any sink, the counter labels, the log record, the error box snapshot, a help query, a dry run, an MCP call, the caller markers, a request for help with no arguments, the setting, settings that cannot load and an unwritable ledger
  - Verification: `$ uv run devops ci test tests/telemetry/test_usage_errors.py`
- [x] 1.2 Add `UsageRecordingGroup`, `UsageTaggedGroup` and `UsageTaggedCommand` to `core/cli.py`, the record and its sinks in `telemetry/usage_errors.py`, the counter, the setting `telemetry.usage_ledger`, the warning, the MCP mark of the dispatcher thread and the `detect-agent` dependency; let the dry-run branch raise the usage error
  - Verification: `$ uv run devops ci test tests/telemetry/test_usage_errors.py`

## 2. Name the implement job as an agent (behavior)

- [x] 2.1 Write a failing test: the shell of an implement step gets `AI_AGENT=devops-implement`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step.py`
- [x] 2.2 Set `AI_AGENT` in `shell_environment`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step.py`

## 3. Documents

- [x] 3.1 Describe the usage-error record in the generator of `docs/TELEMETRY.md` and in `ARCHITECTURE.md`, add the variable to the declared set, and regenerate the documents with `devops docs generate --sync-readme`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #4840 ranks the ledger lines and proposes fixes (`devops telemetry usage-errors`).
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
