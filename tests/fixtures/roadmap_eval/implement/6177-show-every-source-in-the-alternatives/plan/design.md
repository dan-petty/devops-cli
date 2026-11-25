# Design

## Decisions
- **List every source.** The comment writes each source of the reply in the closed block, in the order of the reply, with duplicates removed as before. The owner's rule of 2026-11-17 forbids a cap that loses context.
- **No new bound in the prompt or the schema.** The prompt asks for a few sources as guidance (#6168), and the schema sets no length.

## Rejected alternatives
- **A higher bound**: it is still a cap that can lose context.
- **Sources outside the closed block**: a long list would make the open comment long again.
