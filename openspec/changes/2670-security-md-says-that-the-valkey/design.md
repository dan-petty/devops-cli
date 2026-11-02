# Design

## Decisions

- **Replace the false sentence in place.**: A correction beside the false sentence leaves two opposite statements in the security policy.
- **Keep the paragraph under principle 11.**: The --url option is the accepted case of the MCP input rule, so the paragraph belongs there.
- **Name the six tools in the paragraph.**: docs/MCP_TOOLS.md lists them, so a reader can check the claim.
- **Keep the note that valkey keys, valkey backup and valkey cli are not MCP tools.**: The note is true and tells a reader which commands a model cannot reach.
- **Record the paragraph text as a requirement of the valkey-endpoint capability.**: The paragraph states the input rule of the Valkey tools, and a test can assert its text offline.

## Rejected alternatives

- **Keep the sentence and add a correction below it.**: SECURITY.md principle 11 would then hold two opposite statements about the same commands.
- **Delete the whole --url paragraph.**: The paragraph records the accepted case of the --url option, which principle 11 needs.
