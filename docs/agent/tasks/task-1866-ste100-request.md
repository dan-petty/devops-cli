# Task: Agents and devops ai Write in ASD-STE100 Simplified Technical English (#1866)

**Issue**: [#1866](https://github.com/dan-petty/devops-cli/issues/1866)
**Scope**: type/docs, scope/ai, scope/docs
**Feasibility**: The author checked this on 2026-10-22. The author read the client code and ran the new tests at the HTTP edge. Every free-text call reaches `chat_messages` or `chat_messages_stream`, so one helper call in each method covers all callers. The evidence is in the section "Feasibility Evidence".

## Description

The owner decided on 2026-10-22 that agents and the product write in ASD-STE100 Simplified Technical English. The project asks for the style in its instructions and prompts. It does not check the style. No test, linter or gate measures it.

- **The rule.** `AGENTS.md` has one bullet, "Write in ASD-STE100 Simplified Technical English". It names the text that it covers and lists the limits. Other bullets are shorter by more characters than the new bullet adds, and their meaning is the same. The file stays under its 40,000-character cap.
- **The request to the models.** `src/devops_cli/ai/tasks/style_ste100.md` holds the request in about 120 words. `src/devops_cli/ai/client/style_request.py` appends it to the system prompt. `chat_messages` and `chat_messages_stream` call it once at their start, before the cache key and the token count read `system`. A system prompt that already holds the request comes back unchanged.
- **Structured calls.** `chat_structured` puts the request after the caller's prompt and before the schema instruction. The schema still ends the system prompt.
- **Text that must stay as it is.** The request tells the model to keep code, commands, file names, identifiers, quoted error text and every quotation. A group analysis reply must quote its references byte for byte. Otherwise `_check_doc_quotes` drops the whole output. The request also tells the model to keep search queries and keyword lists as keywords.
- **Calls that return code or data.** The client cannot tell a grader, a code generator or an evaluation-pair call from a free-text call. No per-caller flag exists. The request tells the model to keep an output format that the task sets, such as JSON, code or a score.
- **Existing text.** No existing prompt file and no existing string changes in this item. Existing strings convert when someone edits them.

## Baselines That Move

- **Benchmark reports.** The request lands in the candidate answers and the peer grades of `devops ai benchmark`, because both calls go through `client.chat`. Older benchmark reports do not compare with new ones.
- **Response cache.** The cache key hashes the system prompt as sent. The key changed, so every cached reply is cold after the upgrade.
- **Token baselines.** Every call sends about 150 more prompt tokens. The project estimate, `count_tokens`, counts 147 for the request. Per-call token baselines shift by this amount.
- **Review arms.** `review_prompt_digest` in `src/devops_cli/ai/personas/__init__.py` hashes every `.md` file under `ai/tasks`. The new file changes the digest, so reviews before this change and reviews after it are separate arms of a prompt benchmark.

## Feasibility Evidence

- **Entry points.** `chat` and `chat_structured` call `chat_messages`. `chat_stream` calls `chat_messages_stream`. These two methods are the only entries to `_dispatch_messages` and `_dispatch_stream`, which send `system` to a provider.
- **Cache key.** `chat_messages` makes the response cache key from `system` before it dispatches. The request must join `system` there. `ResponseCache.generate_key` hashes `system.strip()`, so a changed system text gives a new key.
- **Callers.** Every call site in `src/` outside the client reaches one of the two methods. This includes `PydanticAgent` in `src/devops_cli/ai/agents/agent.py`, the review, roadmap, benchmark, chaos and research code, and `devops ai`.
- **Native Pydantic AI paths.** `create_pydantic_ai_agent`, `create_durable_pydantic_agent` and the `direct_*` methods of `LLMClient` have no caller in `src/` outside their own modules. They stay as they are.
- **Token estimate.** The spend recorders call `count_tokens(system)` on the text as dispatched, so the estimate counts the request.
- **Schema order.** The structured path puts the JSON schema at the end of the system text. The new tests pin this order.
- **Shared fake.** The test convention asks for one shared fake at each process edge. This item meets it at the HTTP edge with `route_client`. The shared `ModelFake` replaces the whole client at the factory seam and never runs the injection, so it cannot test this item.
- **New helper.** `with_style_request` is a new helper. Its module, `src/devops_cli/ai/client/style_request.py`, has 19 lines.

## Acceptance Criteria

- [x] `AGENTS.md` has the rule and stays within its cap, at 39,944 of 40,000 characters. It had 39,933 characters. `tests/test_agents_md_claims.py` passes.
- [x] A free-text call carries the request after the caller's system prompt. Before the change, all four calls sent the caller's prompt alone. Now `tests/test_ai_client_style_request.py` reads the request that `chat`, `chat_messages`, `chat_stream` and `chat_messages_stream` send. The test compares the messages to a snapshot. A call with no system prompt sends the request alone.
- [x] A structured call and a call that sets its own format keep their format. The test for a structured call compares the whole system text. The text holds the caller's prompt, the request, the schema instruction and the schema, in that order. The test for a grader checks that its own instruction stays whole and first. It also checks that the request tells the model to keep a format that the task sets.
- [x] The client does not serve a reply that it cached before the request. The test caches a reply under the key of the bare system prompt, and the call reaches the provider. A second identical call comes from the cache.
- [x] The token estimate counts the request. The test compares the prompt tokens in the spend record to the count of the system text as sent.
- [x] `uv run devops docs check` finds the generated documents current.

## Deliverables

- [x] `AGENTS.md`: the rule, and the shorter wording in other bullets.
- [x] `src/devops_cli/ai/tasks/style_ste100.md`, `src/devops_cli/ai/client/style_request.py`, and the calls in `src/devops_cli/ai/client/unified.py` and `src/devops_cli/ai/client/structured.py`.
- [x] `tests/test_ai_client_style_request.py`, its snapshot in `tests/__snapshots__/`, and the system text in `tests/test_ai_client_structured.py`.
- [x] `docs/agent/tasks/task-1866-ste100-request.md` and `changelog.d/1866.md`.
