# Tasks

## 1. Each chat persona gets its prompt, its tools and its RAG terms (behavior)

- [x] 1.1 Write failing tests: the chat prompt of each persona holds its `prompt.md`; no persona gets the default tool set and challenger gets the read-only set; a persona search embeds the terms of its persona, and challenger has terms.
  - Verification: `$ uv run devops ci test tests/ai/personas/test_personas.py tests/ai/tools/test_persona_tools.py tests/ai/rag/test_persona_query_expansion.py`
- [x] 1.2 Add `prompt.md` to `chat_prompt`, key the tool map and the RAG terms on `Persona`, and give challenger its tools and terms.
  - Verification: `$ uv run devops ci test src/devops_cli/ai/personas/__init__.py src/devops_cli/ai/tools/registry.py src/devops_cli/ai/rag/retriever.py`

## 2. Documents

- [x] 2.1 State in `README.md` what each chat persona gets.
  - Verification: `$ uv run devops ci docs`
