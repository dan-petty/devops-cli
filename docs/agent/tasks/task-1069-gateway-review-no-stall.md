# Task: Gateway Review Calls No Longer Stall for About 190 s on Ollama (#1069)

**Issue**: [#1069](https://github.com/dan-petty/devops-cli/issues/1069)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: scope/ai

## Description
During automated code reviews, LLM inference calls through the LiteLLM gateway experienced stalls of ~190 s on Ollama backends. Investigations revealed three compounding causes:
1. **Edge-path cutoffs**: Review calls routed over Cloudflare edge tunnels hit a 100–125 s proxy timeout. Cloudflare returned HTTP 524 / closed the connection with error 125, while the backend Ollama instance continued generating unseen tokens.
2. **Shuffle routing imbalance and missing disconnect cancellation**: The router-wide strategy `simple-shuffle` with `num_retries: 5` randomly dispersed requests across heterogeneous tiers. Three in-flight requests landed on different tiers only 21% of the time, resulting in requests queueing on one backend while others sat idle (82–87.5% of total Ollama time spent waiting in queue). Furthermore, lack of `cancel_on_disconnect: true` meant severed connections wasted GPU cycles.
3. **Double retry layering and whole-page re-execution on HTTP 400**: Tenacity retry transport and unified client dispatch both retried on exceptions (up to 25 attempts). Non-retryable HTTP 4xx (such as 400 Bad Request) triggered repeated whole-page persona reviews (re-executing all 5 personas), and cut connections lingered in `CLOSE-WAIT` state inside the HTTP connection pool.

This deliverable resolves the stall by:
- Directing review traffic to the LAN NodePort via `devops ai gateway connect` (probing `/health/liveliness` and `/model/info` only, avoiding `/health/readiness`), setting `ai.allow_private_network = True`.
- Changing gateway `routing_strategy` to `least-busy` router-wide, configuring `cancel_on_disconnect: true`, and pinning `num_retries: 0` on review model groups.
- Replacing the arbitrary client concurrency cap (16) with slot-based concurrency derived from `DEFAULT_GATEWAY_REVIEW_SLOTS` (sum = 3).
- Establishing a single retry layer in HTTP transport that retries only transient errors (408, 429, 5xx) with `max_retries + 1` total sends, immediately failing non-retryable 4xx errors, isolating persona retries, and actively closing severed or expired connections in `close_expired_connections`.

## Key Changes
- **Gateway ConfigMap & GPU Matrix** (`k8s/llm/gateway/configmap.yaml`, `src/devops_cli/k8s/gpu_matrix.json`):
  - Configured `general_settings.cancel_on_disconnect: true`.
  - Changed `router_settings.routing_strategy: least-busy`.
  - Set `num_retries: 0` on `devops-review` deployments and pinned review groups (`qwen3-coder:30b`, `gpt-oss:20b`).
- **Configuration & Slots Table** (`src/devops_cli/config/defaults.py`, `src/devops_cli/config/__init__.py`):
  - Added `DEFAULT_AI_GATEWAY_SERVICE = "llm-gateway"`.
  - Added `DEFAULT_GATEWAY_REVIEW_SLOTS = {"ollama-48gib": 1, "ollama-24gib": 1, "ollama-16gib": 1}`.
  - Calculated `DEFAULT_GATEWAY_REVIEW_CONCURRENCY = sum(DEFAULT_GATEWAY_REVIEW_SLOTS.values())` (= 3).
- **HTTP Connection Pool Management** (`src/devops_cli/http/pool.py`, `src/devops_cli/ai/retries/__init__.py`, `src/devops_cli/ai/client/network.py`):
  - Implemented `close_expired_connections` to inspect connection pools and proactively close expired or peer-closed connections (`CLOSE-WAIT`).
  - Added `ExpiringConnectionTransport` and `ExpiringAsyncConnectionTransport` wrapping HTTP transports to purge dead connections on each attempt in `finally:`.
  - Added cleanup hook in `request_limited_json`.
- **Single Retry Layer & Isolated Persona Retry** (`src/devops_cli/ai/client/base.py`, `src/devops_cli/ai/client/unified.py`, `src/devops_cli/ai/review/pipeline.py`):
  - Supported `retries == 0` resulting in `max_attempts = 1`.
  - Short-circuited `_retry_chat_dispatch` to immediately record and raise `AICredentialsError`, `AIClientError`, and connection errors without retrying, delegating retries solely to the HTTP transport.
  - Replaced whole-page retry loops in `_execute_page_review_with_backoff` with direct single-page delegation. Non-retryable 4xx errors immediately record into `errored_files` with HTTP status and response body preview.
- **NodePort Connection CLI** (`src/devops_cli/commands/ai_gateway.py`):
  - Implemented `connect_cmd` (`devops ai gateway connect`) using `node_port_address(service="llm-gateway", spec=NodePortSpec(what="LLM gateway", port=4000, port_name="http"))`.
  - Probes only `/health/liveliness` and `/model/info` (avoiding expensive `/health/readiness`), and updates user settings `ai.gateway_url` and `ai.allow_private_network = True`.
- **Tests** (`tests/test_k8s_llm_gateway.py`, `tests/test_gateway_review_stall.py`):
  - Pinned `least-busy`, `cancel_on_disconnect: True`, and `num_retries: 0` in ConfigMap tests.
  - Added unit test suite covering LAN connect, slot table concurrency, connection cleanup, single retry layer on 503, non-retry on 400, and isolated single persona retry.

## Acceptance Criteria
- [x] **Gateway LAN connect**: `devops ai gateway connect` saves the gateway's NodePort URL from `node_port_address`, probing only `/health/liveliness` and `/model/info` (bypassing `/health/readiness`), enabling `ai.allow_private_network = True` so review calls take the LAN path instead of the edge.
- [x] **Cancel on disconnect & zero gateway retries**: Gateway sets `cancel_on_disconnect: true`, and review model groups carry `num_retries: 0` in `configmap.yaml` and `gpu_matrix.json`.
- [x] **Least-busy routing strategy**: Router-wide `routing_strategy` changed from `simple-shuffle` to `least-busy`.
- [x] **Client cap from slots table**: Review in-flight requests are capped at `DEFAULT_GATEWAY_REVIEW_CONCURRENCY = sum(DEFAULT_GATEWAY_REVIEW_SLOTS.values())` (= 3), replacing hardcoded 16.
- [x] **ConfigMap tests pinned**: `tests/test_k8s_llm_gateway.py` verifies `least-busy`, `cancel_on_disconnect: True`, and `num_retries: 0`.
- [x] **Single retry layer**: Transient HTTP statuses (408, 429, 5xx) retry with `max_retries + 1` sends per call on 503; non-retryable 4xx (400) fails without retry and reports status and body preview.
- [x] **Isolated persona retry**: With 5 personas on 1 page and 1 transient 503, exactly 6 calls are sent (not 10).
- [x] **Cut/abandoned connections closed**: `close_expired_connections` purges dead and CLOSE-WAIT connections from the HTTP pool.
- [x] **Recorded measurement procedure**: Documented below with exact LogQL and PromQL queries.
- [x] **Offline unit tests**: All tests run offline, mock external calls, and run in < 1 s per test.
- [x] **Changelog recorded**: `changelog.d/1069.md` records the fix under `### Fixed`.
- [x] **Quality gate**: `uv run devops ci` passes with 100% passing checks and $\ge 90\%$ test coverage.

- Pending a person: `devops ai quiesce` on other clients, run `devops review path <path>`, and verify 0 edge cuts, queue-wait share $\le 10\%$, and 100% LAN traffic.

## Measurement Procedure

To verify gateway performance and validate that review calls take the LAN path without queue stalls:

### 1. Quiesce Ambient Workloads
```bash
uv run devops ai quiesce
```

### 2. Connect to Gateway via LAN NodePort
```bash
uv run devops ai gateway connect
```

### 3. LogQL Queries (Loki)
Inspect Cloudflare tunnel edge cuts (expect: 0):
```logql
{stream="stdout"} |= "error" |= "125"
```
Or for Cloudflared pod specifically:
```logql
{app="cloudflared"} |= "error" |= "125"
```

Inspect Ollama backend chat requests:
```logql
{app="ollama"} |= "/api/chat"
```

### 4. PromQL Queries (Prometheus)
Calculate backend queue-wait share (expect: $\le 10\%$ during review):
```promql
sum(rate(ollama_queue_wait_seconds_sum[5m])) / sum(rate(ollama_total_request_seconds_sum[5m]))
```

Monitor gateway in-flight requests and routing distribution:
```promql
sum by (model) (litellm_in_flight_requests{group="devops-review"})
```

Calculate HTTP status code distribution (expect: 0 edge 524s, 0 unexpected 5xx):
```promql
sum by (status_code) (rate(litellm_requests_total[5m]))
```

### 5. Review Session Output Verification
Run the review session and export metrics into the session directory:
```bash
SESSION_ID=$(uv run devops review branch --dry-run | grep -oE '[0-9]{8}-[0-9]{6}' | head -n 1)
# Inspect session metrics and ledger attempts
cat .data/reviews/${SESSION_ID}/findings.json | jq '.metadata'
```
