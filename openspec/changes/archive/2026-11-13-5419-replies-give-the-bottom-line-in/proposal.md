# Proposal: #5419

## Why

The owner set a rule on 2026-11-13: every reply and every report gives the bottom line in its first line (#5419). The first line tells the reader the action to do or not to do, and each hold. An agent reply opened with "#5407 is done and green", and it put "do not merge it yet" in the middle. A reader who acts on the first line alone can do the wrong thing.

`src/devops_cli/ai/tasks/style_ste100.md` said "Put the result and the decision first". It did not say that a hold, a blocker, a step for a person or a merge order goes in the first line. It did not stop a positive status before a gate that changes it. Agents read this file through rule 9 of `AGENTS.md`, and each model call of `LLMClient` gets it through `src/devops_cli/ai/client/style_request.py`.

## What Changes

- The paragraph of `style_ste100.md` that started "Put the result and the decision first" now asks for the bottom line in the first line: what to do or not do, the real state and each gate.
- The paragraph defines a gate as any hold, blocker, review, person step, merge order or deployment step that still applies. It tells the writer not to start with "done", "green" or "ready" while a gate applies.
- When a reply has many items, the first line says which item to act on now and which item to hold.
- The other sentences of the paragraph stay: give only the detail that the reader needs, and do not tell the steps that you took.
- The rule stays in this one file. `AGENTS.md` is at its character limit, and its rule 9 already links to the file.
- The change alters the system prompt that each model call of `LLMClient` sends, so a consumer can observe it. It carries a delta of the capability `agent-instructions`.

The change fits one pull request.

## Capabilities

- `agent-instructions`: ADDED requirement "The style rules ask for the bottom line in the first line".

## Impact

- Each free-text and structured model call of `LLMClient` sends the new paragraph in its system prompt. A pydantic-ai agent run (`devops ai chat`, `investigate` and the implement step) sends no style request before or after this change. #5424 tracks it. A reply that the cache holds under the old system prompt is not served again, because the cache key holds the system prompt as sent.
- Agents that read `style_ste100.md` through rule 9 of `AGENTS.md` get the new rule.
- The snapshot `tests/ai/__snapshots__/test_ai_client_style_request.ambr` holds the full text of the request, so the pull request regenerates it.
- No command, option, setting or manifest changes.

## Feasibility

- `git show origin/main:src/devops_cli/ai/tasks/style_ste100.md` showed the paragraph "Put the result and the decision first. Then give only the detail that the reader needs to act on it. Do not tell the steps that you took, unless the task asks for them." It holds no rule for a hold, a gate or the first line.
- `src/devops_cli/ai/client/style_request.py` loads `style_ste100.md` with `load_task_prompt` and appends it to the system prompt. `unified.py` and `structured.py` call `with_style_request`, so a change of the file reaches every model call of `LLMClient` with no code change. `git grep -n with_style_request -- src` finds no other caller, so the agent runs of `build_agent` and `investigate` get no style request (#5424).
- `git grep` for a sentence of the file found the text only in `style_ste100.md` and in `tests/ai/__snapshots__/test_ai_client_style_request.ambr`. No eval fixture and no other document holds it.
- `AGENTS.md` rule 9 links to `style_ste100.md`, so agents get the rule with no edit of `AGENTS.md`.

## Existing Tool Considered

No tool. The rule is text in the existing style file, and the existing loader sends it. The issue gives the cost: about 40,000 tokens and 30 minutes elapsed. The change deletes no internal code.
