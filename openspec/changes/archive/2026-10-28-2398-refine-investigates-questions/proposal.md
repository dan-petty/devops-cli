# Proposal

## Why

Issue #2398: `devops roadmap refine --confirm` at bb46660c put 55 items under "Waiting on a person". Refine's last comment on each item shows three causes.

- About 30 items wait on a fact that refine could look up, marked "(missing verified source)", such as "Can Gitleaks scan a directory in one run?" (#2232). Refine plans at most 3 web searches from the body before the model knows its questions, and the model answers one time with the cited files and 5 grepped identifiers. It cannot search the code, read a file or search the web for a question it finds. The run did no web research at all, because no web search key is set, and refine said nothing about it.
- About 20 items wait on key questions that their bodies answer already. `_extract_heading_bullets` takes every bullet under "Key questions" as a question, also nested bullets and statements, and a question counts as answered only when its text is a substring of a question in the reply.
- Some items wait on a design choice that the model gave as a suspected block, such as #1858. The prompt calls a decision "a choice someone makes".

The owner's rule is to decide an open design question with the standard or open-tool answer. Only the decisions that AGENTS.md reserves for a person go to a person. On 2026-10-28 the owner also chose the hosted Firecrawl API as the web search, in place of Tavily.

## What Changes

- **Investigation.** When the validated proposal has a fact or a decision with no verified source, or a body question with no answer, refine runs one pydantic-ai agent for the item. The agent has read-only tools: search the code at the pinned commit, list a directory, read a file or a line range, and search the web through Firecrawl when the repository is public and a key is set. A tool answers each failure as text, so no argument can stop the run. A request and tool-call budget caps the run, and the function tools go when the budget nearly runs out. Each model request streams. The agent returns the revised proposal, which goes through the same validation. A run that stops with no proposal leaves the first proposal in place. A proposal with nothing open makes no investigation request.
- **Decisions by best practice.** A question has one of the kinds `fact`, `decision` and `person`. A decision lists the options it compared, each with the reason it was chosen or rejected. A decision that quotes an owner decision shows "(owner decision)", one with a verified source shows "(best practice)", and one without shows "(proposed)". No decision waits on a person. `person` is only for a decision that AGENTS.md reserves for a person, and it waits on a person. The prompts say that a design choice is never a suspected block.
- **Body questions by number.** The body is parsed as CommonMark. A body key question is a top-level list item under "Key questions" whose first paragraph holds a question mark. Text after its last question mark, or any block inside the item after that paragraph, answers it. The request numbers the other body questions, and an answer names the number of the question it answers. The substring match goes.
- **Web search through Firecrawl.** `firecrawl_search` posts to Firecrawl's `/v2/search` through the egress factory. The setting `firecrawl.api_key`, the variable `DEVOPS_CLI_FIRECRAWL_API_KEY`, the keyring entry `firecrawl_api_key` and its row in Secret `devops/devops-cli` replace Tavily's, with no alias (pre-1.0).
- **Web search state.** When web search is off, the plan says so once and gives the reason.
- The CLI's entry point sets `PYDANTIC_AI_NO_BANNER`, so pydantic-ai prints no banner into the CLI's output.
- Deleted: the research-plan step (`ResearchPlan`, `run_research_step`, `roadmap_refine_research.md`), `_normalize_question`, `tavily_search` and Tavily's setting, variable, keyring entry and secret row. The proposal request carries no `search_results`.
- The reply schema, the next step of an item, the plan's report and the web search key are behavior that a person sees, so the change carries a spec delta that adds requirements to `roadmap-refine`.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine`: ADDED requirements for the investigation, decisions, body questions and the web search state.

## Impact

- `src/devops_cli/roadmap/refine.py`, the new `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/ai/client/factory.py`, `src/devops_cli/ai/common_tools.py`, `src/devops_cli/entry.py`.
- Settings: `src/devops_cli/config/{constants,defaults,env,options,settings}.py`, `src/devops_cli/security/secrets.py`, `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/lang/en/{messages,help}.py`.
- Prompts: `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`, the new `roadmap_refine_investigation.md` and `roadmap_refine_reply.md`; `roadmap_refine_research.md` goes.
- Documents: `README.md`, `k8s/README.md` and the generated references.
- Tests: `tests/test_roadmap_refine.py`, the new `tests/test_roadmap_refine_investigation.py`, `tests/support/fakes/model.py`, `tests/test_common_tools.py`, the egress, secret, push-secrets and startup tests.
- #1849 changes the same reply schema and prompt. The second of the two to merge rebases onto the first.

## Feasibility

- Refine's comments at bb46660c (read with `devops gh api repos/dan-petty/devops-cli/issues/<n>/comments`) give the three causes and their counts above.
- `devops gh api repos/dan-petty/devops-cli --jq .private` is `false`, and no web search key is in the workstation configuration or in Secret `devops/devops-cli` (`kubectl get secret -o json | jq '.data | keys'`).
- Firecrawl's API reference (docs.firecrawl.dev, read on 2026-10-28): `POST https://api.firecrawl.dev/v2/search` with `Authorization: Bearer <key>` and a body of `query` and `limit` (default 10, at most 100) returns `{"success": true, "data": {"web": [{"url", "title", "description", ...}]}}`. A result's page content comes only with `scrapeOptions`, which costs a credit for each scraped result.
- The Firecrawl Python SDK (`firecrawl`, `firecrawl/v2/utils/http_client.py`) calls `requests.post` and takes no session or client, so a call through it would bypass the egress factory that SECURITY.md item 2 requires.
- `Settings` reads its file with `extra="ignore"`, so a `tavily:` section in an existing `config.yaml` is ignored, not an error.
- markdown-it-py 4.2.0 is a declared dependency (`pyproject.toml`) that `rag/chunker.py` and `research/edges.py` use. Its CommonMark tokens give each list item's nesting level, its first paragraph with the wrapped lines in one inline token, and each fence and heading level.
- pydantic-ai 2.54.0, the pinned version, has `Agent(model, output_type=..., instructions=..., tools=..., retries=..., capabilities=...)`, `Agent.run_sync(..., usage_limits=..., event_stream_handler=...)`, the `PrepareTools` capability with `RunContext.usage` and `usage_limits`, `capture_run_messages`, `UsageLimitExceeded`, `UnexpectedModelBehavior`, `ModelHTTPError.status_code` and `BANNER_ENABLED` / `PYDANTIC_AI_NO_BANNER` (read in the installed `pydantic_ai/agent/__init__.py`, `agent/abstract.py`, `usage.py`, `_run_context.py`, `capabilities/prepare_tools.py`, `exceptions.py` and `_display.py`). With an event stream handler, `agent/abstract.py` streams each model request node through `model.request_stream`. `UnexpectedModelBehavior` also ends a run whose tool calls exceed their retries (`ToolManager`).
- `resolve_pydantic_ai_model` (`src/devops_cli/ai/pydantic_ai_bridge.py`) sends a model of provider `gateway` as an OpenAI chat model to the gateway URL with the AI key, and sets its `served_by` to that URL. Its provider uses `new_async_http_client`, so the egress check applies.
- A chat request with one tool to the `analysis` model through the gateway (`ollama_chat/qwen3.8:27b` in `k8s/llm/gateway/config.yaml`) returned `finish_reason: tool_calls` and a native `tool_calls` entry. With the investigation under `ToolOutput` and no web search key, the model called `list_files`, `search_code` and `read_file` natively, and a plan-only `devops roadmap refine --item 2234` settled two of the item's four open facts (the request plan's model and the rate limiter at `src/devops_cli/github/rate_limiter.py`). The two left open ask whether the local git calls of `pr create` count as requests, and which issue comes first, which no file of the repository answers. Under `PromptedOutput` the same model wrote its tool calls as JSON text and the run failed. `NativeOutput` sends the schema as `response_format`, which Ollama turns into a grammar for every reply, so the model could call no tool.
- A pydantic-ai run records no spend: `LLMClient` records it in `_record_response_telemetry_and_spend`, and the bridge's provider does not. The investigation records the run's usage with `track_request_spend`.
- The Service runs a round in a worker thread (`src/devops_cli/server/service.py`), where `Agent.run_sync` starts its own event loop.

## Existing Tool Considered

pydantic-ai's agent runs the tool loop, its `ToolOutput` reads the final proposal, its `UsageLimits` caps the run, and its `PrepareTools` capability ends the loop before the cap. pydantic-ai is the project's model library. `PydanticAgent` in `src/devops_cli/ai/agents/` is not used: it finds a tool call by parsing the model's text, it adds a RAG step and memory, and `LLMClient`, which it calls, has no native tool calls. markdown-it-py parses the body's key questions. `git grep`, `git ls-tree` and `git show` read the pinned commit as refine does today. Nothing new is built for the loop or the parser.

Firecrawl's hosted API is the web search. Its SDK is not used, because it bypasses the egress factory, so `firecrawl_search` is a direct REST call: about 30 lines and 4 tests, as `tavily_search` was, at a build cost of about 20,000 tokens and 10 minutes, with nothing to keep in step with the SDK beyond the documented `/v2/search` request and reply.

The change deletes `ResearchPlan`, `run_research_step`, `roadmap_refine_research.md`, `_normalize_question`, the substring match of body questions, `tavily_search`, Tavily's setting, variable, keyring entry and secret row, and their tests.
