# Proposal

## Why

Issue #2637. The MCP tool `ai_prewarm` published the option `url`. The model that calls the tool fills it in. `devops ai prewarm` used that URL as the only Ollama node. `_preload_single_ollama_url` sent `POST {url}/api/generate` with a JSON body. The client dials at the configured level, which admits loopback without `ai.allow_private_network`.

A URL can end in `?x=`. Then the path of the request is the path that the caller wrote, and `/api/generate` is only the value of the query. A model could send a POST request to any path of any loopback service of the host. The tool also told the model whether the answer was HTTP 200.

The cause is the same as in #2480 and #2634: input from a caller is used as configuration.

## What Changes

- The MCP tool `ai_prewarm` publishes no `url` option. It prewarms or evicts the servers of `ai.ollama_urls`. A call that gives `url` fails at the argument contract. It sends no request.
- The tool keeps its other options: `model`, `keep_alive`, `all_nodes`, `evict`, `output_format` and `json_output`.
- `devops ai prewarm` keeps `--url` for a person at the command line. The POST body holds the model name and the keep-alive value, and no credential. So no rule for a credential is needed.
- A consumer sees the tool schema and the requests, so the change carries a spec delta. It creates the capability `ai-prewarm` with one requirement.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `ai-prewarm`: the servers that `devops ai prewarm` and its MCP tool send requests to.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/mcp/generator.py`.
- `tests/test_ai_prewarm.py`.
- `docs/MCP_TOOLS.md` (generated).

## Feasibility

- On `origin/main` at `5bb1ed0f`, an offline probe showed the defect. It ran with `HOME` in a temporary directory, the null keyring, `ai.provider` set to `ollama` and `ai.allow_private_network` unset. It bound a listener on `127.0.0.1` and called `ai_prewarm` through a FastMCP `Client`, with `url=http://127.0.0.1:<port>/v1/sys/seal-status?x=`.
  - The listener received `POST /v1/sys/seal-status?x=/api/generate HTTP/1.1` with the body `{"model":"FAKE-2637-model","prompt":"","keep_alive":"1h"}`.
  - The tool replied `confirmed HTTP 200 (keep_alive=1h)`.
- `generate_mcp_tools` publishes each Click option of a command. `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` is the existing way to publish fewer options, and #2480 and #2634 use it. `ArgumentContractMiddleware` refuses a parameter that the published schema does not name.
- `CONST_MCP_EXPOSURE_TABLE` marks `ai prewarm` as not read-only, and `docs/MCP_TOOLS.md` shows `readOnlyHint: false`. The tool posts and changes which models a server holds in memory, so the mark is right.
- `devops ai prewarm` takes its servers from `_resolve_prewarm_urls`. Without `--url`, it takes all of `ai.ollama_urls`, or the first one with `--single-node`. The tool needs nothing else.
- `_preload_single_ollama_url` builds its client at the configured egress level and checks the URL with `validate_base_url`. The level is right for the servers of `ai.ollama_urls`. It admits loopback, which is the usual Ollama address, and private addresses only with `ai.allow_private_network`.
- No other path gives a model a prewarm URL. `preload_models` has two other callers, `prewarm_async` and the chat prewarm, and both use `ai.ollama_urls`.

## Existing Tool Considered

The change uses `_PATH_PARAM_RESTRICTIONS` of the MCP generator and the argument contract of the MCP server. Both exist, and #2480 and #2634 use both. So the change builds no new function. It adds one entry to an existing table.

The change deletes the `url` option of the MCP tool `ai_prewarm`. It deletes the POST to a path that a model chooses.
