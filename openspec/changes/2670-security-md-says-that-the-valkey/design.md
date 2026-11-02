# Design

## Decisions

- **Replace the false sentence in place.**: A correction beside the false sentence leaves two opposite statements in the security policy.
- **Keep the paragraph under principle 11.**: The --url option is the accepted case of the MCP input rule, so the paragraph belongs there.
- **Name the six tools in the paragraph.**: docs/MCP_TOOLS.md lists them, so a reader can check the claim.
- **Keep the note that valkey keys, valkey backup and valkey cli are not MCP tools.**: The note is true (`tests/ai/mcp/test_mcp.py` lists the three as excluded) and tells a reader which commands a model cannot reach.
- **Check the result with `git grep`, not with a test of the prose.**: A test that reads SECURITY.md would freeze the words of a policy document. The rule itself is held in code: the `valkey-endpoint` requirement `The MCP Valkey tools publish no URL` and its tests.

## Rejected alternatives

- **Keep the sentence and add a correction below it.**: SECURITY.md principle 11 would then hold two opposite statements about the same commands.
- **Delete the whole --url paragraph.**: The paragraph records the accepted case of the --url option, which principle 11 needs.
- **Add a requirement to the `valkey-endpoint` spec for the text of the paragraph.**: `openspec/specs/valkey-endpoint/spec.md` line 104 already holds the rule for the tools. A second requirement about prose would repeat it, and `openspec/config.yaml` gives a document-only change no spec delta.
