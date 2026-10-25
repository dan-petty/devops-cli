# Proposal

## Why

In #1432, proxied Kubernetes service requests fail on clusters that use token authentication because the proxy sends a `BearerToken` header instead of `Authorization`. Also, the pod informer passes a lambda wrapper to the watch stream, which prevents type resolution and emits untyped objects without retry backoff.

## What Changes

This change fits into one pull request.

Observable behavior changes:
- `k8s://` proxy calls authenticate through `Configuration.auth_settings()`, transmitting the standard `Authorization` header for token configurations and calling the token refresh hook before each request.
- The pod informer invokes `Watch.stream` directly with typed list functions (`list_namespaced_pod` and `list_pod_for_all_namespaces`), yielding typed `V1Pod` models.
- The informer reconnect loop applies exponential backoff through `tenacity` on failures and resumes from the last seen `resourceVersion`.
- The informer relists cluster resources when the API server answers with HTTP 410 Gone.
- Documentation in `SECURITY.md` and `README.md` clarifies that the `k8s://` proxy is checked at connect time while the in-process `kubernetes` client is not.

## Capabilities

### New Capabilities
- `k8s-service-proxy`: Proxied service requests authenticate with the Kubernetes client configuration auth settings and invoke token refresh hooks.
- `k8s-informer`: Pod informer streams typed pod objects directly, reconnects with exponential backoff, and recovers from expired watch bookmarks with relisting.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/k8s/service_proxy.py`: Header extraction uses `configuration.auth_settings()` and executes `refresh_api_key_hook`.
- `src/devops_cli/k8s/informer.py`: Removes lambda wrapper from `Watch.stream`, adds exponential backoff, stores `resourceVersion`, and handles 410 Gone relisting.
- `tests/k8s_fakes.py`: Adds `:rtype: V1PodList` docstrings and watch streaming support to `FakeCoreV1`.
- `SECURITY.md`, `README.md`: Updates connection check descriptions.

## Feasibility

The premise was verified against upstream packages and real runtime behavior:
- `kubernetes` 36.0.3 `Configuration.auth_settings()` maps tokens under `BearerToken` or `authorization` to `{'BearerToken': {'type': 'api_key', 'in': 'header', 'key': 'authorization', 'value': 'Bearer ...'}}`.
- Invoking `configuration.refresh_api_key_hook(configuration)` populates rotated credentials before `auth_settings()` is read.
- `kubernetes.watch.Watch.get_return_type` inspects the function docstring for `:rtype:`. Lambdas lack this docstring and produce empty return types, whereas direct API function references return `V1Pod`.
- `tenacity.Retrying` combined with `threading.Event.wait` delivers exponential backoff while allowing clean interruption on `informer.stop()`.

## Existing Tool Considered

The change uses the built-in authentication and streaming capabilities of the `kubernetes` Python package and `tenacity`. It removes the hand-rolled header mapping logic in `_auth_headers` and replaces the unbacked-off infinite loop in `_run_watch_loop`.
