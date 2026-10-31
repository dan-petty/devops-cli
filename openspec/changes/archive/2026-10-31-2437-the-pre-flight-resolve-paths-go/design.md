# Design

## Decisions

- **Delete pre-flight resolve paths without shims**: The project is alpha software prior to 1.0.0. No backward compatibility shims are preserved.
- **Rewire kept pre-flight checks to vet_addresses**: Callers that do not dial through an httpx2 client (Qdrant, kubectl manifest URL, docker engine) or that dial nothing (config init wizard) invoke `vet_addresses` at their level. Each caller documents its time-of-check gap in a docstring.
- **Factory accepts optional transport**: `new_http_client` and `new_async_http_client` accept `transport: httpx2.BaseTransport | None = None` to support test and preview injection, allowing `ai/client/base.py` to eliminate direct calls to `httpx2.Client`.
- **Config init wizard uses configured level**: The init wizard uses `configured_level` (loopback admitted without `ai.allow_private_network`, private admitted with the flag). It catches `httpcore2.ConnectError` and SSRF refusals.
- **ast-grep rules for continuous gating**: Two ast-grep rules enforce zero raw client construction outside `http/client.py` and zero calls to deleted resolve paths.

## Rejected Alternatives

- **Keep pre-flight validation as a shim**: Violates the zero backwards compatibility principle for pre-1.0 software.
- **Single egress level for all pre-flight callers**: Different callers dial different network scopes. Using a single level would be either too permissive or too restrictive.
- **Allowing raw httpx2.Client for MockTransport**: Violates the acceptance criterion that no raw client exists outside `http/client.py`.
