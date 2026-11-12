# Tasks

## 1. Behavior: the read-only flag of a tool follows the local writes of its command

- [ ] 1.1 Add the failing tests to `tests/invariants/test_dry_run_class_ratchet.py`: the audit of the read-only flags reports a local writer with a read-only tool, a command that writes nothing with a tool that is not read-only, and a local writer that is not a `no-external-request` row of the table; the audit of the repository table finds no mismatch with the six local writers
  - Verification: `$ uv run devops ci test tests/invariants/test_dry_run_class_ratchet.py`
- [ ] 1.2 Mark the entries of `ai quiesce`, `ai resume`, `ai failover`, `ai gateway failover`, `review export-feedback` and `ai ingest library` in `CONST_MCP_EXPOSURE_TABLE` not read-only, and say in the comment of the table that a tool whose command writes local state or a file is not read-only
  - Verification: `$ uv run devops ci test tests/invariants/test_dry_run_class_ratchet.py tests/ai/mcp/test_mcp_read_only_write_options.py tests/ai/mcp/test_mcp_tool_registry.py`

## 2. Documents

- [ ] 2.1 Regenerate `docs/MCP_TOOLS.md`, so that it shows `false` for the six tools
  - Verification: `$ uv run devops docs generate --check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
