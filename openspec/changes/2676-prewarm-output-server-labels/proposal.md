# Proposal

## Why

Issue #2676: `devops ai prewarm` and `devops ai preload` name each Ollama server by the URL text of `ai.ollama_urls`. The MCP tool `ai_prewarm` returns that text to the model that calls it. A user name or a query value in the URL shows in full. The rule of #1110 and #2481 is that a reply names a server by its host and port.

The counter `devops_cli_ai_prewarms_total` also takes its label `model` from the `model` argument of the tool. The calling model sets that text, so the label can hold any characters and any length.

## What Changes

- `devops ai prewarm` names each server as `host[:port]` in the table, and keys `nodes` of the JSON and YAML output by the same text. The MCP tool `ai_prewarm` returns that output.
- `devops ai preload` names each server as `host[:port]`.
- Two URLs of one host and port make one node. The node is ok only when both URLs are ok.
- The label `model` of `devops_cli_ai_prewarms_total` keeps only the characters `A-Z a-z 0-9 . _ : / -` and at most 128 of them. Each other character becomes `_`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-prewarm`: adds the requirements for the server name and for the model label.

## Impact

- `src/devops_cli/commands/ai.py`: the output of `prewarm` and `preload`, and the counter label.
- `src/devops_cli/telemetry/instruments.py`: the helper that bounds a label value.
- `docs/TELEMETRY.md` is generated from the instrument text, so it follows the instrument if that text changes.

## Feasibility

- The premise holds. On `origin/main`, `OllamaProviderMixin._preload_single_ollama_url` returns the raw `url` as the key of the result, `_render_prewarm_results` and `preload` print or serialize that key, and `prewarm` emits `"model": str(target_model)`. A test with the real client and the shared network fakes shows `http://FAKE-2676-user@example.com:11434/?x=FAKE-2676-query` in the reply of the MCP tool and in the output of both commands.
- The issue is not superseded. #2637 removed the `url` parameter of the tool, so the tool takes no URL from the model. It did not change the output. `server_label` of #2481 exists in `src/devops_cli/ai/benchmark/labels.py` and has no caller in the prewarm path.
- The issue gives the label character set `a-zA-Z0-9._-`. Real Ollama model names hold `:` and `/` (`gemma4:26b`, `hf.co/org/repo:Q4_K_M`), and an existing test expects `gemma4:26b`. The change keeps `:` and `/`. The example of the issue, `my/model`@v2`.0!beta`, keeps `/` too.
- The issue says a URL with no port shows as `example.net:80`. `server_label` drops the default port of the scheme, as the benchmarks do (#2481), so that URL shows as `example.com`. The change keeps this one naming rule.
- `http://example.com` and `https://example.com` give the same label, so they merge into one node that is ok only when both are ok. A reader cannot tell which scheme failed. The change keeps the rule that a failure never hides.

## Existing Tool Considered

`server_label` of #2481 covers the server name: it uses `get_url_origin` and `origin_label`, so the change writes no URL parser. No library bounds a metric label value for this counter, and the OpenTelemetry SDK only drops values over a limit that it does not set for a counter attribute. The change adds one helper of a few lines, `bounded_label`, with a regular expression and a slice. The cost is about 300 tokens to write and keep it. The change deletes no code.
