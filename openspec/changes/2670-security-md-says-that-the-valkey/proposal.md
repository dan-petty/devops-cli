# Proposal

## Why

SECURITY.md principle 11 states that the devops valkey commands are not MCP tools (#2670). Six of the nine commands are MCP tools, so a reader may think that a model cannot reach a Valkey command. The rule that matters is different: the six tools publish no URL, and a person types --url at the command line.

## What Changes

- Rewrite the --url paragraph under principle 11 of SECURITY.md.
- Name the six valkey commands that are MCP tools: valkey_ping, valkey_stats, valkey_info, valkey_get, valkey_set and valkey_flush.
- State that the six tools publish no url option.
- State that a person types --url at the command line and no model gives the URL.
- Remove the sentence 'Those commands are not MCP tools.'
- Add one requirement to the valkey-endpoint spec for the text of the paragraph.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `valkey-endpoint`: Security policy states the Valkey MCP tool input rule

## Impact

- Documents: `SECURITY.md`

## Feasibility

- The premise holds. SECURITY.md principle 11 ends its --url paragraph with 'Those commands are not MCP tools.'
- docs/MCP_TOOLS.md lists valkey_ping, valkey_stats, valkey_info, valkey_get, valkey_set and valkey_flush as tools, so six of the nine commands are MCP tools.
- The first check reads the false sentence: `git grep -n "Those commands are not MCP tools" SECURITY.md`.
- The second check reads the six tools: `git grep -n "valkey_" docs/MCP_TOOLS.md`.
- The change edits one paragraph of SECURITY.md and needs no code, no cluster and no network.

## Existing Tool Considered

No open tool or library covers this need. The change corrects a factual error in the project's own security policy document. The cost is one edited paragraph in SECURITY.md: no code to build, keep or fix, and no elapsed time beyond the edit. The change deletes no internal code.
