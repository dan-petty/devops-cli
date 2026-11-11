# Design

## Decisions

- Delete by prefix: one statement deletes each span attribute of `llm-gateway` whose name starts with `request.` or `response.`. Traces do not need the management bodies, and the prefix also covers a body field that a later LiteLLM version adds.
- Scope the statement to `llm-gateway` with the same condition as the hex replacement. The management hooks are LiteLLM code, so the statement does not touch the spans of other services.
- The statement goes in the `span` group only. The management hooks write span attributes, not event attributes.

## Rejected alternatives

- One delete rule for each field (`request.key`, `request.callback_vars`): LiteLLM has many management endpoints with an `http_request` argument, and each body field becomes an attribute. A list of names misses the next field that holds a secret.
- A value pattern for a raw `sk-` key: `callback_vars` holds secrets of other services that have no common form, so a value pattern does not find them.
- Turn on `LITELLM_OTEL_V2` in the gateway, which skips the management hook: it changes the full span model of the gateway and is not in the scope of a fix. The Collector rule also protects the spans if the gateway setting changes.
