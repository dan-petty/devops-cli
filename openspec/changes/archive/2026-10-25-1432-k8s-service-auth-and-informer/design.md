# Design

## Context

See `proposal.md` for background and problem motivation.

Proxied Kubernetes requests are constructed in `src/devops_cli/k8s/service_proxy.py`. Pod event watching and caching are managed in `src/devops_cli/k8s/informer.py`. Test cluster doubles reside in `tests/k8s_fakes.py`.

## Goals / Non-Goals

**Goals:**
- Extract proxy request authorization headers from `configuration.auth_settings()` after invoking `refresh_api_key_hook`.
- Stream typed pod events directly using typed function references to preserve `V1Pod` deserialization.
- Reconnect watch streams using `tenacity` exponential backoff, resuming from the latest `resourceVersion`.
- Relist resources upon encountering HTTP 410 Gone.
- Support watch streaming and return type annotations in `FakeCoreV1`.
- Align egress connection documentation with actual system checks.

**Non-Goals:**
- Replacing the in-process `kubernetes` client or its `urllib3` transport.
- Implementing informers for other Kubernetes resource kinds.

## Decisions

### Decision 1: Per-request auth header generation via `Configuration.auth_settings()`
`resolve_proxy_target` and `resolve_proxy_connection` generate headers per request from `configuration.auth_settings()`.
*Rationale:* `Configuration.auth_settings()` maps `BearerToken` and `authorization` keys to `Authorization: Bearer <token>`.
*Rejected Alternative:* Extending custom dictionary checks for `BearerToken`. Rejected because upstream `Configuration.auth_settings()` is the canonical source of truth in the `kubernetes` package.

### Decision 2: Explicit invocation of `refresh_api_key_hook`
If `refresh_api_key_hook` is defined on `configuration`, call it before reading `auth_settings()`.
*Rationale:* In-cluster and exec credential plugins rotate tokens through this hook. If `api_key` is initially empty, `auth_settings()` does not trigger the hook.
*Rejected Alternative:* Relying solely on `auth_settings()` to trigger the hook. Rejected because inspection showed that `Configuration.auth_settings()` only calls the hook if a key is already present.

### Decision 3: Direct API function references for `Watch.stream`
Pass `core_v1.list_namespaced_pod` (with `namespace=...`) or `core_v1.list_pod_for_all_namespaces` directly into `w.stream` without a lambda wrapper.
*Rationale:* `Watch.get_return_type` reads `:rtype:` from function docstrings. Direct functions retain `:rtype: V1PodList`, allowing deserialization into `V1Pod` instances.
*Rejected Alternative:* Attaching artificial docstrings to lambda wrappers. Rejected as brittle and unnecessary because `Watch.stream` accepts keyword arguments directly.

### Decision 4: Tenacity exponential backoff with event-driven sleep
Wrap the informer reconnection loop in `tenacity.Retrying` with `wait_exponential`, delegating sleep to `threading.Event.wait`.
*Rationale:* Exponential backoff prevents tight retry loops on persistent errors. Sleeping against a stop event ensures that `informer.stop()` interrupts the sleep immediately.
*Rejected Alternative:* Standard `time.sleep()`. Rejected because long backoff intervals would block worker thread shutdown.

## Risks / Trade-offs

- [Risk] Reconnect backoff blocks worker thread termination. → Mitigation: Sleep uses `self._stop_event.wait(delay)`, which awakens immediately on `stop()`.
- [Risk] Expired watch bookmarks trigger repeating 410 Gone errors. → Mitigation: Encountering 410 Gone triggers relisting, which fetches the newest `resourceVersion` and updates the cache.
