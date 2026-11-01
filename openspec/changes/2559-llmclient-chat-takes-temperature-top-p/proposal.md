# Proposal

## Why

Issue #2559: `LLMClient.chat` and `LLMClient.chat_messages` take `**kwargs` and use none of them. A caller that passes `temperature`, `top_p` or `seed` gets no error. The request carries the sampling of the client's config. Review group analysis (`_chat_and_judge` in `src/devops_cli/review/analysis.py`) passes all three from its `SamplingRecord` on each call, so it believes it sets them.

## What Changes

- `chat` and `chat_messages` take `temperature`, `top_p` and `seed` as named keyword parameters. They no longer take `**kwargs`, so an unknown keyword is a `TypeError`.
- One `CallSampling` value (a `NamedTuple` in `src/devops_cli/ai/client/models.py`) carries the three values through `_retry_chat_dispatch`, `_dispatch_messages` and `_invoke_provider_messages` to the provider driver and its payload builder.
- A per-call `temperature` or `top_p` replaces the configured one. A parameter that the caller omits keeps the configured value. `AIConfig` has no seed, so no seed is sent unless the caller passes one.
- The gate that exists today decides whether sampling is sent at all, and it also gates a per-call value: `use_model_sampling` and, for the OpenAI-compatible driver, a reasoning model send no sampling. The seed follows the same gate.
- Claude takes no seed. Its request carries the per-call `temperature` and `top_p` in `extra_body` under the sampling gate that exists today, and never a seed.
- The reply cache key holds the per-call `temperature` and `top_p` in place of the configured ones. It adds `seed` only when a seed is sent.
- The description of `use_model_sampling` says that the request also omits the seed. The generated configuration document follows.
- The change carries a spec delta in `ai-model-sampling`, because the request body of the model client and a setting description are observable. It modifies two requirements and adds three.
- Out of scope: `chat_messages_stream` and the streamed drivers, which no caller gives a per-call value, and the `gen_ai.request.temperature` span attribute, which still reads the config.
- The change fits one pull request. It has four groups: the OpenAI-compatible request with the cache key and the TypeError, the Ollama request, the Claude request, and the setting description.

## Acceptance

The criteria of #2559 (the refine block of the issue), and the group that delivers each:

- The request body carries the `temperature`, `top_p` and `seed` that the caller passes: group 1 for the gateway, `openai` and `copilot` providers, group 2 for Ollama, group 3 for Claude (temperature and top_p only).
- The cache key holds the per-call `temperature`, `top_p` and `seed`: group 1.
- A caller that omits a parameter gets the configured `temperature` and `top_p`: group 1, and the same test for each provider in groups 2 and 3.
- An unknown keyword raises `TypeError`: group 1.
- The request omits `seed` for a provider that does not support it (Claude): group 3.
- The sentence in the settings description that `use_model_sampling` also omits the seed is no criterion of the issue. It follows from the decision that the seed uses the sampling gate, so the document does not become wrong: group 4.

## Impact

- Code: `src/devops_cli/ai/client/unified.py`, `src/devops_cli/ai/client/models.py`, `src/devops_cli/ai/client/openai.py`, `src/devops_cli/ai/client/ollama.py`, `src/devops_cli/ai/client/claude.py`, `src/devops_cli/config/settings.py` (two description strings).
- Documents: `docs/CONFIGURATION.md`, which `devops docs generate --sync-readme` writes.
- Tests: `tests/ai/client/test_per_call_sampling.py` (new) and `tests/ai/client/test_claude_provider.py`. Four test fakes of a provider driver have a fixed signature and take the new `sampling` keyword: `tests/ai/client/test_ai_client_telemetry.py`, `tests/ai/client/test_ai_client_finish_reasons.py`, `tests/ai/client/test_ai_request_priority.py` and `tests/ai/spend/test_ai_spend_dispatch.py`.
- Callers: review group analysis starts to send its seed (42) and its temperature and top_p through the task's own client. Its reply cache key also holds the seed, so earlier cached analysis replies miss once.
- The code and the specs that stay as they are, and must keep passing:
  - `_apply_sampling_and_limits`, `_build_ollama_payload` and `_build_anthropic_kwargs` are extended, not copied. The pins `tests/ai/test_ai_model_sampling.py` (calls `_prepare_params("sys", [], stream=...)`), `tests/ai/client/test_batch_2_review_defects.py` and the parity test in `tests/ai/client/test_claude_provider.py` call them with no sampling and keep their results.
  - The existing requirements "Streamed calls preserve sampling and trace headers" and "Claude provider capability-driven sampling parity" in `openspec/specs/ai-model-sampling/spec.md` stay true.
  - `route_client` in `tests/llm_stream_fakes.py` is the fake model at the HTTP edge. The new tests use it, as `tests/ai/client/test_ai_client_retries.py` does.
  - No caller of `LLMClient.chat` or `chat_messages` in `src/` or `tests/` passes a keyword that is not a named parameter (see Feasibility), so removing `**kwargs` breaks none.
  - Change #2175 (open) deletes `LLMClient._get_ollama_semaphore` in `unified.py`, far from the lines this change edits. The two changes do not modify one requirement.

## Feasibility

Each fact comes from a run on `origin/main` at 4fe2de28, on 2026-11-01.

- The defect is real. `git grep -n "kwargs: Any" origin/main -- src/devops_cli/ai/client/unified.py` prints `unified.py:526` (in `chat`) and `unified.py:761` (in `chat_messages`). `chat` forwards `**kwargs` to `chat_messages`, and `chat_messages` reads none.
- The caller exists. `src/devops_cli/review/analysis.py:1079` calls `llm_client.chat(system_prompt, user_prompt, temperature=sampling.temperature, top_p=sampling.top_p, seed=sampling.seed, max_retries=0, validator=accept)`. `SamplingRecord.seed` defaults to `DEFAULT_ANALYSIS_SAMPLING_SEED`, which is 42 (`src/devops_cli/config/defaults.py:910`).
- The issue reproduces. A gateway client with `temperature=0.1, top_p=0.95`, routed to a fake model at the HTTP edge with `route_client` (probe script in the scratch folder, not committed), calls `chat("sys", "user", temperature=0.9, seed=7)`. The request body holds `{'temperature': 0.1, 'top_p': 0.95}` and no seed. `chat("sys", "user", unknown_param=1)` prints `no TypeError`.
- The payload builders read only the config: `git grep -n 'getattr(self._config, "temperature"\|getattr(config, "temperature"' -- src/devops_cli/ai/client` prints `claude.py:145`, `ollama.py:298`, `openai.py:169`, `unified.py:401` and `unified.py:790`. Line 790 is the cache key.
- The code has no seed. `git grep -nw seed -- src/devops_cli/ai/client src/devops_cli/config` prints one line, `src/devops_cli/config/defaults.py:401`, a comment about defect corpora. So `AIConfig` has no seed, there is no config fallback for it, and each driver gets new seed code.
- Guards exist and a per-call value must obey them. `openai.py:156` (`_apply_sampling_and_limits`) returns before sampling for a reasoning model, and `openai.py:168` skips it when `use_model_sampling` is true. `ollama.py:297` has the same `use_model_sampling` guard. `claude.py:138` sends sampling only when the model declares support, no adaptive thinking runs, and `use_model_sampling` is false. `unified.py:784` to `798` set the cache `temperature` and `top_p` to `None` under `use_model_sampling` or `supports_reasoning`. The spec "Model-level sampling option" says a request omits `temperature` and `top_p` under `use_model_sampling`. So the decision of design.md is that the gate wins over a per-call value.
- The libraries accept the values. `uv run python` with `inspect.signature` shows `seed` in `openai.resources.chat.completions.Completions.create` (openai 3.26.1). The same check on `anthropic.resources.messages.Messages.create` (anthropic 1.12.1) shows no `seed` and no `temperature` parameter. The Anthropic driver already sends sampling through `extra_body` (`claude.py:143` to `150`), so it keeps that path and omits the seed. The Ollama Modelfile reference (`raw.githubusercontent.com/ollama/ollama/main/docs/modelfile.mdx`) lists `seed`, `temperature` and `top_p` as parameters, and the chat API takes them in `options`.
- Removing `**kwargs` breaks no caller. An AST scan of `src` and `tests` for `.chat(` and `.chat_messages(` calls with a keyword that is not a named parameter lists only calls on test doubles (`TestModel` and `FunctionModel` in `src/devops_cli/ai/agents/testing.py`, `tests/support/fakes/model.py`, a review test fake) and calls that pass `**kwargs` or `**options` to the real client with known keys: `src/devops_cli/ai/review/runner.py:258` (a helper whose only callers are tests, with no keyword) and `tests/ai/spend/test_ai_spend_dispatch.py:197` (`append_cache`). The one other keyword found, `agent_name` in `tests/ai/agents/test_ai_agent_capabilities.py:349`, goes to a `FunctionModel`.
- Fixed-signature test fakes exist. `_ollama_messages` is replaced by fakes with a fixed signature in `tests/ai/client/test_ai_client_telemetry.py` (`_reply`), `tests/ai/client/test_ai_client_finish_reasons.py` (`provider`), `tests/ai/client/test_ai_request_priority.py` (`fake_messages`) and `tests/ai/spend/test_ai_spend_dispatch.py` (`_cut_reply`). `_claude_messages` is replaced by `_claude_reply` in `tests/ai/client/test_ai_client_telemetry.py`. The fakes of `_openai_compat_messages` all take `**_` or `**kwargs`. The new keyword breaks the fixed ones, so groups 2 and 3 update them.
- Nothing newer did or removed this. `git log --since=2026-10-28` on the four client files lists commits (#2930, #2887 and others) and none changes sampling. `git grep -nw seed` above still prints only the one comment line. `git grep -ln ai-model-sampling -- openspec/changes` outside this folder and the archive prints nothing, so no active change modifies the requirements that this change modifies. The only open issue that mentions `seed` and `temperature` is #2559 (`devops gh api 'search/issues?q=repo:dan-petty/devops-cli+seed+temperature+in:title,body+state:open'`).
- The setting description appears in `src/devops_cli/config/settings.py:532` and `:647` and in `docs/CONFIGURATION.md:201`. `git grep -n "neither temperature nor top_p"` prints only those three lines, and no test pins the text.

## Existing Tool Considered

No new tool is needed. The OpenAI-compatible API, Ollama and the Anthropic Messages API take sampling per request, and the installed SDKs show it (see Feasibility). The change passes the caller's values through the code that exists and deletes nothing but the ignored `**kwargs`. The cost to build it is a few hundred lines across five files in `src/devops_cli/ai/client/`, plus tests.
