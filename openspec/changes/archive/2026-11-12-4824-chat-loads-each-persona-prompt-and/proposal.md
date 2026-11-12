# Proposal: #4824

## Why
The chat prompt of a persona is `role.md` and `tasks/chat.md`. It drops `prompt.md`, so the debate rules of challenger and the threat model of devsecops never reach `devops ai chat`. The tool map has no challenger entry, so challenger gets the default set of 194 tools. The RAG expansion matches parts of the persona name ("sec", "arch") and has no challenger branch. Closes #4824.

## What Changes
- The chat prompt is `role.md`, `tasks/chat.md` and `prompt.md`, in the order of the review prompt.
- The tool map is keyed on the `Persona` enum and has one entry for each persona. Challenger gets a read-only set: `read_file`, `list_files`, `search_code`, `git_diff`, `git_status` and `rag_search`. A name that is not a `Persona` raises `ValueError`; it gets no default set.
- The RAG expansion is a table keyed on the `Persona` enum. Challenger adds decision and trade-off terms. A name that is not a `Persona` keeps the query as it is.

## Capabilities
- New: `ai-chat-personas`.

## Impact
- `src/devops_cli/ai/personas/__init__.py`, `src/devops_cli/ai/tools/registry.py`, `src/devops_cli/ai/rag/retriever.py`.
- The chat prompt of each persona is larger by its `prompt.md` (devsecops: 1,421 to 6,214 characters). Challenger sends 6 tool schemas, not 194.
- `README.md` states what each chat persona gets.

## Feasibility
- `src/devops_cli/ai/personas/__init__.py:69` builds `chat_prompt` from `role` and `_get_task_chat()` only. `system_prompt` on the line before it adds `domain`.
- `_build_persona_tool_map` in `src/devops_cli/ai/tools/registry.py` has 5 keys, and `get_persona_tools("challenger")` returns `get_default_tools()`: 194 tools on `origin/main`.
- `_expand_persona_rag_query` in `src/devops_cli/ai/rag/retriever.py` gives the security terms to any name that holds "sec", such as "security-lead", and none to challenger.
- The new tests fail on `origin/main` for each of these three causes.

## Existing Tool Considered
A fix of project code. No tool applies. Cost to build: about 40,000 tokens and 1 hour.
