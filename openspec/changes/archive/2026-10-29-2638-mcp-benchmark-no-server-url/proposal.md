# Proposal

## Why

Issue #2638. The MCP tool `ai_benchmark` published the options `servers` and `models`. The model that calls the tool fills them in. `servers` is a list of Ollama URLs. A `models` entry can be `model@url`, and the command reads the URL as the server for that model. The benchmark sent `POST {url}/api/chat` to each URL, with a prompt in the body. The client dials at the configured level, which admits loopback without `ai.allow_private_network`.

A URL can end in `?x=`. Then the path of the request is the path that the caller wrote, and `/api/chat` is only the value of the query. A model could send many POST requests to any path of any loopback service of the host.

The cause is the same as in #2480, #2634 and #2637: input from a caller is used as configuration.

## What Changes

- The MCP tool `ai_benchmark` publishes no `servers` option. It benchmarks on the servers of `ai.ollama_urls`. A call that gives `servers` fails at the argument contract. It sends no request.
- The tool refuses a `models` entry of the form `model@url` before any command runs. The error names the option `models`. The tool keeps plain model names.
- `devops ai benchmark` keeps `--servers` and the `model@url` form for a person at the command line.
- The help text of `--models` says that the MCP tool refuses a `model@url`. The generated documents carry the text.
- The message `ERRORS.mcp.model_names_endpoint` was in the tree and no code used it. It now names the option `models` and is the refusal message of the tool.
- A consumer sees the tool schema and the requests, so the change carries a spec delta. It creates the capability `ai-benchmark` with one requirement.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `ai-benchmark`: the servers that `devops ai benchmark` and its MCP tool send requests to, and the part that a caller has in choosing them.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/mcp/generator.py`.
- `src/devops_cli/lang/en/errors.py` and `src/devops_cli/lang/en/help.py`.
- `tests/test_ai_benchmark_mcp_tool.py`.
- `docs/MCP_TOOLS.md`, `docs/CLI_REFERENCE.md` and `docs/commands/ai.md` (generated).

## Feasibility

- On `origin/main` at `9e8317bb`, the new tests showed the defect. They ran through a FastMCP `Client`, with `ai.provider` set to `ollama`, `ai.allow_private_network` set to false and `record_connects` of `tests/web_fakes.py` with canned chat answers.
  - A call with `servers` set to `http://127.0.0.1:8200/v1/sys/seal-status?x=` and `models` set to `qwen3:0.6b` did not fail. The recorder held dials and written request bytes.
  - A call with `models` set to `qwen3:0.6b@http://127.0.0.1:8200/v1/sys/seal-status?x=` did not fail, and it also wrote requests.
- `generate_mcp_tools` publishes each Click option of a command. `_PATH_PARAM_RESTRICTIONS` is the existing way to publish fewer options, and #2480, #2634 and #2637 use it. `ArgumentContractMiddleware` refuses a parameter that the published schema does not name.
- A JSON Schema `pattern` on `models` does not fit. `test_every_published_keyword_is_one_a_refusal_can_describe` holds that every published keyword has a kind and a description in the refusal tables, so a `pattern` needs a new kind and new text in the contract layer. A check before dispatch, as `_check_sandbox_preconditions` does, needs no new keyword.
- `parse_model_spec` in `src/devops_cli/ai/benchmark/model_spec.py` is the one place that reads the `@` of `model@url`. The tool check calls it, so the tool and the command cannot disagree on what names a server.
- A hand-written MCP tool of release v0.2.25 refused a model with an endpoint, with `ERRORS.mcp.model_names_endpoint`. The generated tool replaced it and the check was not carried over. The message stayed in the tree with no caller (`git log -S model_names_endpoint`).
- The configured servers need loopback: the usual Ollama server is `http://localhost:11434`. The tests show that the tool dials the configured server at the configured level.

## Existing Tool Considered

The change uses `_PATH_PARAM_RESTRICTIONS` of the MCP generator, the argument contract of the MCP server and `parse_model_spec` of the benchmark. All three exist, and the first two serve #2480, #2634 and #2637. The change adds one table entry, one short check and no new helper to parse a URL or a model name.

The change deletes the `servers` option of the MCP tool, the `model@url` form of its `models` option, and the unused wording of `model_names_endpoint`.
