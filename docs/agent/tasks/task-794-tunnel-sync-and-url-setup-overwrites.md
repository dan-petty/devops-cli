# Task 794: Tunnel Sync and URL Setup Route and Setting Preservation

**Issue**: [#794](https://github.com/dan-petty/devops-cli/issues/794)
**Feasibility**: Verified Cloudflare API v4 tunnel configurations endpoint schema, warp-routing and originRequest field structures, and Kubernetes ingress service discovery matching patterns against live schema definitions.
**Scope**: `type/bug`, `scope/k8s`, `priority/p1-high`

---

## 1. Description & Objectives

Cloudflare tunnel sync and Kubernetes URL setup previously overwrote settings they should preserve. Tunnel sync dropped per-route `originRequest` fields (`noTLSVerify`, `httpHostHeader`), replaced a custom catch-all route with `http_status:404`, and when the GET of the current config failed it silently fell back to a full replace that wiped `warp-routing` and user-added routes. URL setup matched ingress services by bare substrings (`"ai"`, `"llm-gateway"`) instead of using `CONST_K8S_INGRESS_SERVICE_PATTERNS`, and `_should_update_url` let a newly discovered FQDN overwrite a user-set remote custom `ai.gateway_url`.

This fix makes tunnel sync preserve every field of routes it keeps, preserves custom catch-all and `warp-routing` blocks, aborts without sending PUT if GET fails, ensures `--dry-run` makes no network calls while printing serialized GET and PUT payloads, ensures gateway ingress discovery uses `CONST_K8S_INGRESS_SERVICE_PATTERNS` with exact service-name and namespace matching, prevents `_should_update_url` from overwriting remote custom URLs, and covers the deleted-tunnel filter and valkey port guard.

#### Key Deliverables:
- Model enhancement: `CloudflareTunnelIngressRule` preserves `originRequest` (`origin_request`), and `CloudflareTunnelConfig` preserves `warp-routing` (`warp_routing`).
- Route merging: `_merge_tunnel_ingress_rules` preserves pre-existing custom catch-all rules rather than unconditionally overwriting with `http_status:404`.
- Update payload: `update_tunnel_configuration` serializes `originRequest` on kept routes and preserves `base_config` (`warp-routing`).
- Read failure guard: `sync_tunnel_routes` raises an error if reading existing tunnel configuration fails and sends no PUT request.
- Dry run: `tunnel_sync --dry-run` makes zero network requests and prints serialized GET and PUT payloads.
- Gateway discovery: `_find_gateway_ingress_url` uses `CONST_K8S_INGRESS_SERVICE_PATTERNS` with exact service-name and namespace matching instead of bare substring matching.
- URL protection: `_should_update_url` forbids overwriting existing remote FQDN endpoints (such as `ai.gateway_url`).
- Valkey guard: `_should_update_valkey` prevents overwriting valkey configuration with a non-default port.
- Comprehensive unit and integration test coverage across all acceptance criteria.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
