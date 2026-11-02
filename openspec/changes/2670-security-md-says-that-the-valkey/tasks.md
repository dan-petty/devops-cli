# Tasks

## 1. Correct the Valkey paragraph in SECURITY.md

Reads: `SECURITY.md`, `docs/MCP_TOOLS.md`. Changes: `SECURITY.md`.

- [ ] 1.1 Rewrite the --url paragraph under principle 11 of `SECURITY.md`. State that six of the nine `devops valkey` commands are MCP tools: `valkey_ping`, `valkey_stats`, `valkey_info`, `valkey_get`, `valkey_set` and `valkey_flush`. State that these tools publish no `url` option. State that a person types `--url` at the command line and no model gives the URL. State that `valkey keys`, `valkey backup` and `valkey cli` are not MCP tools. Remove the sentence `Those commands are not MCP tools.`, and verify that `! git grep -n "Those commands are not MCP tools" SECURITY.md` passes
- [ ] 1.2 SECURITY.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
