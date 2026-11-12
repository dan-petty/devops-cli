# Design

## Decisions
- The chat prompt adds `prompt.md` after the chat task, as the review prompt adds it after the review task. The persona prompt then comes last and states the focus of the persona.
- The tool map and the RAG terms are dictionaries keyed on `Persona`. The test of the tool map checks each member, so a new persona with no entry fails a test, not a chat.
- `get_persona_tools` converts the name with `Persona(name)`. The chat command and the pipeline give only `Persona` values, so an unknown name is a programming error and raises `ValueError`.
- The RAG expansion keeps the query for a name that is not a `Persona`, because `investigate_rag_context` takes any string.
- Challenger reads and searches only. It argues against a claim and names the evidence that settles it, so it needs the code, the diff and the knowledge base, and no scanner, cluster or MCP tool.

## Rejected alternatives
- Keep the default set as the fallback of the tool map. The fallback hid the missing challenger entry, and it sends 194 tool schemas.
- Keep the substring match and add a challenger branch. The match gives the terms of one persona to a name of another, such as "security-lead".
