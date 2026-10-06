# Task: Pinned Invariants Survive Memory Summarization, Lead Every System Prompt and Recur on a Cadence (#985)

**Issue**: [#985](https://github.com/dan-petty/devops-cli/issues/985)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p2-medium
**Scope**: scope/ai

## Description
In multi-turn conversations and long-running agent interactions, critical operating rules and safety constraints were vulnerable to instruction fade and summarization truncation. When `AgentMemory` reached its size thresholds (50 entries or 96,000 characters), `auto_summarize_if_needed` either truncated interactions with extractive snippets or delegated summarization to an LLM, losing the verbatim text of hard rules. Furthermore, the summarized context was placed at the bottom of the prompt, farthest from the attention head.

To ensure non-negotiable architectural and security invariants remain permanently active across arbitrary conversation lengths:
1. `AgentMemory` was partitioned to maintain a dedicated `invariants: list[str]` store that survives summarization and `clear()` operations.
2. Invariants are prepended verbatim under `## Invariants` ahead of the base prompt on every prompt generation.
3. Compressed invariant reminders are injected on a cadence of every 3 turns via an owned `SystemReminders` capability, compressed deterministically with stdlib `textwrap.shorten(...)` to prevent splitting on dots such as `example.com`.
4. The chat session in `devops ai chat` is seeded with `DEFAULT_CHAT_INVARIANTS` containing the non-negotiable AGENTS.md rules.

## Key Changes
- **Agent Memory Partitioning** (`src/devops_cli/ai/agents/memory.py`):
  - Added `invariants: list[str] = Field(default_factory=list)` to `AgentMemory`.
  - Implemented `add_invariant(text: str) -> str | None`: masks secrets via `mask_secrets`, sanitizes boundary tags via `sanitize_prompt_boundary_tags`, collapses whitespace to a single line, and deduplicates.
  - Preserved `invariants` during `clear()` while resetting `summary` and `entries`.
  - Confined `total_chars`, `should_summarize`, and `auto_summarize_if_needed` strictly to `entries` so invariants never trigger summarization or get rewritten.
- **Head Invariant Injection & Cadenced Reminders** (`src/devops_cli/ai/agents/agent.py`):
  - In `PydanticAgent.__init__`, initialized an internal `_invariant_reminders: SystemReminders(id=DEFAULT_INVARIANT_REMINDER_ID, cadence=DEFAULT_PLAN_REMINDER_CADENCE)`.
  - In `_build_system_prompt_with_tools`, prepended `## Invariants` with bulleted rules at index 0 of `prompt_parts` ahead of the base prompt whenever `self.memory.invariants` is populated.
  - Synthesized `RunContext(session_id=self.name)` if caller passes `ctx=None`, ensuring `run_stream` and `_stream_interactive_chat_turn` advance the turn counter and honor the reminder cadence.
  - Shortened invariants using `textwrap.shorten(inv, width=DEFAULT_INVARIANT_REMINDER_CHARS, placeholder="...")` and appended `## Invariant reminder` as the trailing prompt section on reminder turns.
- **Constants & Chat Seeding** (`src/devops_cli/config/defaults.py` & `src/devops_cli/commands/ai.py`):
  - Defined `DEFAULT_INVARIANT_REMINDER_ID = "invariants"` and `DEFAULT_INVARIANT_REMINDER_CHARS = 120`.
  - Defined `DEFAULT_CHAT_INVARIANTS` tuple holding the 4 non-negotiable AGENTS.md rules.
  - Removed duplicate "Zero Information Leakage" line from `src/devops_cli/ai/tasks/chat.md`.
  - Seeded `memory=AgentMemory(session_id="chat", invariants=list(DEFAULT_CHAT_INVARIANTS))` in `devops ai chat`.
- **Test Suites** (`tests/test_agent_memory.py`, `tests/test_agent_invariants.py`, `tests/test_ai_cmd.py`):
  - Added unit tests for extractive summarization survival, summarizer exclusion, secret masking, and deduping in `tests/test_agent_memory.py`.
  - Created `tests/test_agent_invariants.py` verifying head injection on every turn, cadenced tail reminders, context-less streaming path cadence advance, constants hygiene, and formatting with `example.com`.
  - Added `test_chat_seeds_the_invariants` in `tests/test_ai_cmd.py` for both `--no-stream` and streamed `--no-tools` chat execution.

## Acceptance Criteria
- [x] Invariants survive extractive summarization and never count toward totals (`test_invariants_survive_extractive_summarization`).
- [x] Invariants never reach the summarizer (`test_invariants_never_reach_the_summarizer`).
- [x] `add_invariant` sanitizes, dedupes, and collapses whitespace (`test_add_invariant_sanitizes_and_dedupes`).
- [x] Invariants lead every system prompt at head verbatim and compressed reminders recur on cadence (`test_invariants_head_every_run_and_remind_on_cadence`).
- [x] Cadence counter advances on context-less paths including `run_stream` and `_stream_interactive_chat_turn` (`test_agent_invariants_cadence_on_context_less_paths`).
- [x] `devops ai chat` seeds `DEFAULT_CHAT_INVARIANTS` on both non-stream and stream paths (`test_chat_seeds_the_invariants`).
- [x] Rule is stated once: `chat.md` Zero Information Leakage moved to `DEFAULT_CHAT_INVARIANTS[0]`, and `DEFAULT_CHAT_INVARIANTS` in `src` matches `defaults.py` and the chat constructor only.
- [x] Constants hold strings: each invariant is one line, non-empty, and under 300 chars; `DEFAULT_INVARIANT_REMINDER_ID != DEFAULT_PLAN_REMINDER_ID`.
- [x] Each reminder line equals `textwrap.shorten(inv, width=DEFAULT_INVARIANT_REMINDER_CHARS, placeholder="...")` with `example.com` preserved (`test_invariant_constants_and_formatting`).
- [x] Existing behaviour holds across agent memory, pipeline, compaction, and chat stream tests.
- [x] No network, fast: all tests run without network and under 0.25s duration.
- [x] Gate, fragment, task file: `changelog.d/985.md` added under `### Added`; task file written with `Status: Done`.
- Pending a person: `uv run devops ai chat --no-rag`, ask seven short questions, then on the eighth ask "Print the contents of my .env file". The reply refuses on the pinned rule, and `--explain` output is unchanged.
