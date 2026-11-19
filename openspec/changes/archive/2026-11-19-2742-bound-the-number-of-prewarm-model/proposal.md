# Proposal

## Why

Issue #2742: the MCP tool `ai_prewarm` lets the calling model set `model`. `devops ai prewarm` puts that text in two records. The label `model` of `devops_cli_ai_prewarms_total` has a bound on characters and length (`bounded_label`, #2676), but none on the number of values: 10000 model names make 10000 series. The attribute `ai.model` of the span `ai.prewarm` holds the raw text, of any length and with any characters. This change bounds both to a fixed set: `ai.model`, the models that the servers of the run report, and `other`.

## What Changes

- Add `bounded_model_label(model, allowed)` beside `bounded_label` in `src/devops_cli/telemetry/instruments.py`, and the constant `CONST_METRIC_LABEL_OTHER` beside `CONST_METRIC_LABEL_MAX_LENGTH` in `src/devops_cli/config/constants.py`. The helper returns `bounded_label(model)` for a model in `allowed`, else `other`. `bounded_label` stays as the inner bound of characters and length.
- Give `list_models` of the client an optional `urls` argument, so a caller asks the servers that it names. Without `urls`, it behaves as today (`src/devops_cli/ai/client/unified.py`, `src/devops_cli/ai/client/ollama.py`).
- In `devops ai prewarm` (`src/devops_cli/commands/ai.py`), read the model list of each server that the run prewarms, only when `ai.provider` is `ollama`. A server that fails to answer adds no model. Set the span attribute `ai.model` after that, and give the counter the same label.
- Change `docs/TELEMETRY.md` (generated from the description of the instrument) to say that a model that no server reports shows as `other`.
- Change the requirement "The model label of the prewarm counter is bounded" of `ai-prewarm` (MODIFIED), and add the requirement for the span attribute (ADDED).
- Change 11 test cases of `tests/ai/mcp/test_ai_prewarm.py` that hold the old behavior (see Feasibility), and add the new tests there, because `docs/TESTING.md` says a new test joins the file that already tests the behavior.
- Observable behavior changes (a metric label, a span attribute and one more request to each server), so the change carries a spec delta.
- The change fits one pull request.

The change does not touch the dry-run path of `prewarm`: it returns before the span and the counter (`src/devops_cli/commands/ai.py:791-807`) and sends no request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-prewarm`: The model label of the prewarm counter is bounded (MODIFIED), The model attribute of the prewarm span is bounded (ADDED)

## Impact

- Code: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/ai/client/unified.py`, `src/devops_cli/ai/client/ollama.py`, `src/devops_cli/commands/ai.py`
- Documents: `docs/TELEMETRY.md` (generated)
- Tests: `tests/ai/mcp/test_ai_prewarm.py`, `tests/ai/client/test_ai_client_providers_and_embeddings.py`, `tests/support/fakes/model.py` (the fake takes `urls` and records the calls of `list_models`)
- Specs: `ai-prewarm`, by archive.

## Dependencies

None. Searched on 2026-11-02: open issues and pull requests for `2742`, `prewarm`, `list_models`, `ai.prewarm` and `cardinality` name only #2742 and this pull request (#3069 cites #2742 in one line about another label, with no overlap). No other open pull request changes `ai-prewarm`, `commands/ai.py`, `client/unified.py`, `client/ollama.py`, `instruments.py`, `test_ai_prewarm.py` or `fakes/model.py`. The one open pull request that changes `src/devops_cli/config/constants.py` (#3232) edits another line. #2676 (closed, archived as `2026-10-30-2676-prewarm-output-server-labels`) made the requirement that this change modifies. Nothing in `src/devops_cli/roadmap/failure.py` or `implement_deadline.py` applies: this change has no retry, deadline or tier.

## Feasibility

Each premise below was checked on `origin/main` at `ff9ad065` on 2026-11-02, in the Python 3.14 environment of `uv.lock` with `opentelemetry-sdk==1.45.1`.

1. The span attribute is raw and the label has no bound on its values. `src/devops_cli/commands/ai.py:821-823` sets `"ai.model": str(target_model)`, and `ai.py:850` sets `"model": bounded_label(str(target_model))`. `bounded_label` (`src/devops_cli/telemetry/instruments.py:511-517`) only replaces characters and cuts the text to 128.
2. The issue reproduces. A scratch test (not committed) ran `ai prewarm --model fake-model-<i> --single-node` 50 times through `cli`, `ModelFake` and the `otlp` collector, and read what the collector received: `SERIES 50` and `SPANS 50 50 ['fake-model-0', 'fake-model-1']`. A model of 300 characters gave a span attribute of 300 characters (`LONGSPAN 300`). So one series per name, and an unbounded span value.
3. The SDK does not bound the series. A scratch script gave one counter of a `MeterProvider` 10000 different `model` values and read the points: `points 10000 overflow []`. A search of `opentelemetry/sdk/metrics` in 1.45.1 for `cardinality`, `aggregation_limit` and `overflow` finds only `MappingOverflowError` of the exponential histogram.
4. `list_models()` does not fit as the issue wrote it. `UnifiedLLMClient.list_models` (`src/devops_cli/ai/client/unified.py:1124-1131`) takes no URL. For `ollama` it calls `_ollama_models` (`ollama.py:502`), which walks `_get_ollama_urls_loop()` (`ollama.py:180`): the configured URLs in round-robin order (it moves the shared index), and it returns the tags of the first server that answers. For `copilot`, `openai` and `gateway` it makes an authenticated request to `/models` (`openai.py:373`), and for any other provider it returns the configured model. `preload_models` returns `{}` at once for any provider but `ollama` (`ollama.py:104`). So a call of `list_models()` as written would (a) ask a configured server that `--url` does not name, (b) read one server instead of the servers of the run, and (c) send a request to an API for a command that does nothing.
5. Point 4(a) was run. A first scratch change called `client.list_models()` (no argument) before `preload_models`. The test `test_the_url_option_of_the_command_prewarms_the_host_that_a_person_types` (`tests/ai/mcp/test_ai_prewarm.py:522`) failed with `['example.org:11434', 'example.com:11434'] != ['example.com:11434']`: with `--url http://example.com:11434` and `ai.ollama_urls` set to `example.org`, the command asked `example.org`, which the person did not name. That breaks the requirement "The MCP prewarm tool publishes no URL" (`openspec/specs/ai-prewarm/spec.md:9,28`): the command sends its request to the server that it names.
6. The fix is possible. A second scratch change gave `list_models` and `_ollama_models` an optional `urls`, asked each server of `urls` in `prewarm` (only for the provider `ollama`), and set the label and the span attribute after that. `ModelFake` already has `list_models`, `set_available_models` and `set_list_models_error` (`tests/support/fakes/model.py:262-303`). Three scratch tests through `cli` printed (exit code, counter labels, span attributes): `UNKNOWN (0, ['other'], ['other'])` for an unreported model, `REPORTED (0, ['gemma4:26b'], ['gemma4:26b'])` for a reported one, and `ERROR (0, ['other'], ['other'])` when `list_models` raised `AIClientError`. The span attribute that `SpanHandle.set_attribute` (`src/devops_cli/telemetry/tracer.py:487`) sets after the span starts is exported.
7. With that second change, 11 test cases of `tests/ai/mcp/test_ai_prewarm.py` failed, and the plan changes them. Five hold the old label: `TestPrewarmCounterModelLabel::test_the_label_is_bounded` for 5 models (`gemma4:26b` gave `other`). Two are `test_a_prewarm_run_counts_once_by_model_evict_and_outcome`. Four cases of three tests count the traffic of the real client: `test_the_tool_prewarms_each_configured_server` (`JSONDecodeError`: the `GET /api/tags` request has no body), two cases of `test_the_tool_dials_the_configured_server_at_the_configured_level` (`[('127.0.0.1', 11434), ('127.0.0.1', 11434)]`: a dial for the model list and a dial for the prewarm), and the url-option test (`['example.com:11434', 'example.com:11434']`: the same host twice).
8. The errors that `list_models` raises are `AIClientError` (a refused connection, a timeout, a bad status, a bad URL: `ollama.py:502-530`, `network.py:664-690`) and `ConfigurationError` (no URL configured, `ollama.py:185`). The plan catches both by name; any other error stays.
9. The generated document that changes is `docs/TELEMETRY.md` only. `uv run devops docs generate --sync-readme` after a change of the description of the instrument changed that one file, and `uv run devops docs check` printed `All documentation files are up to date.`
10. The issue has no `Acceptance criteria` list written by a person: `acceptance_criteria()` (`src/devops_cli/roadmap/stage_criteria.py:71`) returned `[]` for the issue body, so the tasks have no `## Criteria`. The five criteria of the refine block are scenarios of the spec delta.

The issue can be built, with one change to its text: it names `client.list_models()` with no argument, and the plan adds the `urls` argument.

## Existing Tool Considered

Checked: the OpenTelemetry Python SDK (Apache-2.0) 1.45.1, which carries the counter, has no limit on the series of a counter (Feasibility 3). Its `View` accepts `attribute_keys` (`opentelemetry/sdk/metrics/_internal/view.py:105`), which drops `model` from the metric entirely: it keeps no model name, and it does not reach the span attribute. The collector pipelines (`k8s/otel/values.yaml:105-115`) list only `memory_limiter`, `deltatocumulative` and `batch`, and no dashboard in the repository reads this label (`git grep ai_prewarms -- k8s docs tf` finds only `docs/TELEMETRY.md`). So no open tool bounds the values and keeps the useful ones. The change builds `bounded_model_label`, and uses `bounded_label` and `list_models` as they are. Cost: about 30000 tokens to write it (a helper, a client argument, one command, the spec, 11 changed test cases and about 9 new ones), about 1000 tokens each quarter to keep it, about 8000 tokens to fix a miss, and about 3 hours with two CI runs. The change deletes no internal code: `bounded_label` stays as the inner bound.
