# Task: Service URLs bracket IPv6 hosts; k8s:// addresses reach only their Service (#1111)

**Issue**: [#1111](https://github.com/dan-petty/devops-cli/issues/1111)
**Status**: Done
**Milestone**: v0.2.32
**Priority**: priority/p2-medium
**Scope**: scope/k8s

## Description
Service, node, and API-proxy URLs previously assembled with f-strings and string concatenation produced unbracketed IPv6 URLs (such as `http://2001:db8::1:30080`), causing URL parsers in `httpx2` and `urllib.parse` to raise invalid port exceptions. In addition, `configure-urls` failed when inspecting IPv6 clusters, Kubernetes Service proxy paths accepted unvalidated identifiers and dot segments (`..`, `.`, `%2e%2e`) that traversed outside the Service proxy boundary carrying kubeconfig credentials, and HTTPS probe targets were probed over HTTP.

This deliverable resolves these defects:
1. URL builders across `commands/k8s/networking.py`, `k8s/service.py`, `telemetry/collector.py`, and `sandbox/probe.py` construct URLs using `httpx2.URL(scheme=..., host=..., port=...)`, which brackets IPv6 addresses (including `::ffff:192.0.2.1` and `fe80::1%eth0`).
2. `_resolve_accessible_url` resolves ports via `httpx2.URL(url).origin.port` (retaining scheme default ports like port 80 for LoadBalancers) and handles unbracketed IPv6 inputs gracefully without raising.
3. `ServiceRef` validates namespace, service, and port identifiers against Kubernetes RFC 1123 label constraints (`validate_k8s_identifier(..., namespace=True)`), raising `ServiceAddressError`.
4. Refuses dot segments (`_has_dot_segments`) across `ServiceRef`, `proxy_path`, and `get_json` for direct and `k8s://` addresses, preventing directory traversal escapes.
5. `resolve_proxy_target` and `resolve_proxy_connection` preserve API server path prefixes and raw encodings, cleanly splitting base URL and prefix.
6. Sandbox probe uses `httpx2.Origin` to probe `https://` targets over HTTPS and appends paths via `append_path`.
7. `port_forward` formats addresses using `httpx2.URL` before `subprocess.Popen` with fallback to `{address}:{lport}` on `InvalidURL`, preventing detached orphan processes.

## Acceptance Criteria Checklist
- [x] Offline table test verifies IPv6 bracketing across node, LoadBalancer, collector, Jaeger OTel, and probe builders.
- [x] `::ffff:192.0.2.1` and `fe80::1%eth0` bracket and round-trip cleanly with `urlsplit` and `httpx2.URL`.
- [x] Port-forward message prints bracketed IPv6 and raw address lists without raising.
- [x] `configure-urls` handles IPv6 NodePort and LoadBalancer endpoints and falls back safely to loopback.
- [x] Unreachable port-80 LoadBalancer falls back to `http://localhost:80`.
- [x] Proxy URL target resolution and Qdrant base/prefix split preserve cluster paths and raw prefixes.
- [x] Suffixes `foo:bar`, `.hidden`, and `a..b` pass dot segment checks; dot segments (`..`, `.`, `%2e%2e`) and invalid identifiers are refused with `ServiceAddressError`.
- [x] `devops k8s service-url` CLI exits 1 with no traceback on invalid identifiers.
- [x] Probe dispatches over HTTPS for HTTPS targets, preserves paths and query parameters, and brackets IPv6.
- [x] Existing IPv4 and proxy test suites pass without regression.
- Pending a person: on a dual-stack or IPv6-only cluster, if one is available, `devops k8s configure-urls` writes bracketed URLs that the dashboard reaches.
