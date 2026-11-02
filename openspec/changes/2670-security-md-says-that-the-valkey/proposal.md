# Proposal

## Why

SECURITY.md principle 11 states that the devops valkey commands are not MCP tools (#2670). Six of the nine commands are MCP tools, so a reader may think that a model cannot reach a Valkey command. The rule that matters is different: the six tools publish no URL, and a person types --url at the command line.

## What Changes

- Rewrite the --url paragraph under principle 11 of SECURITY.md.
- Name the six valkey commands that are MCP tools: valkey_ping, valkey_stats, valkey_info, valkey_get, valkey_set and valkey_flush.
- State that the six tools publish no url option.
- State that a person types --url at the command line and no model gives the URL.
- Keep the note that valkey keys, valkey backup and valkey cli are not MCP tools.
- Remove the sentence 'Those commands are not MCP tools.'
- The change has no spec delta and sets `skip_specs: true`. It edits the prose of a policy document, and no consumer observes prose as a behavior. The requirement `The MCP Valkey tools publish no URL` of the `valkey-endpoint` spec (line 104) already holds the rule in code terms: the same six tools, no `url` parameter, and `--url` kept on the nine commands.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `SECURITY.md`

## Feasibility

Checked on 2026-11-02 at `origin/main` (24ef67ac).

- The false sentence exists. `git grep -n "Those commands are not MCP tools" SECURITY.md` prints line 34, the last sentence of the `--url` paragraph under principle 11. No other Markdown file outside the archive and `CHANGELOG.md` holds it (`git grep -n "not MCP tools"`).
- Six commands are MCP tools. `git grep -n '("valkey", ' src/devops_cli/config/constants.py` finds six rows of `CONST_MCP_EXPOSURE_TABLE` (lines 401-406): flush, get, info, ping, set and stats. `docs/MCP_TOOLS.md` is generated from this table and lists `valkey_flush`, `valkey_get`, `valkey_info`, `valkey_ping`, `valkey_set` and `valkey_stats` (lines 145-150).
- Nine commands exist. `git grep -c '^@app.command' src/devops_cli/commands/valkey.py` prints 9. The table has no row for `keys`, `backup` or `cli`, and `tests/ai/mcp/test_mcp.py` (lines 644-646) lists the three as excluded from MCP. So the note about these three stays true.
- The six tools publish no `url`. `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` (lines 34-45) allows only `section`, `key`, `value`, `ex`, `all_databases` and `dry_run`. The tool sections of `docs/MCP_TOOLS.md` (lines 2340-2412) list no `url` row.
- The issue has no acceptance criteria of its own: the `Acceptance criteria` heading sits inside the refine block, which the criteria check cuts off (`acceptance_criteria` in `src/devops_cli/roadmap/stage_criteria.py`). So the plan has no `## Criteria` section.
- The change edits one paragraph of SECURITY.md and needs no code, no cluster and no network.

## Existing Tool Considered

No open tool or library covers this need. The change corrects a factual error in the project's own security policy document. The cost is one edited paragraph in SECURITY.md: about 3,000 tokens to read the paragraph and the table and to write the new text, no code to keep or fix, and about 5 minutes of one session. The change deletes no internal code.
