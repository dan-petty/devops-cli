# Design

## Decisions

**The fallback is the constant that the default already uses.** `otel_service_name` falls back to `CONST_OTEL_SERVICE_NAME` only when the variable is unset, and an empty value is a set variable. `gateway_caller_headers` now applies the same constant to an empty value, so the default and the empty case agree.

**The test extends the existing fixture.** The header test already runs the chat, the embedding and the agent path with a named and a default service. A third `service_name` parameter with an empty value checks every path with one line of test code.

## Rejected alternatives

- **Change `otel_service_name` itself.** The telemetry resource keeps the empty name that a workload set, and the fallback belongs to the header that the gateway reads.
- **Send `unknown`.** The gateway series would then hold a second name that no workload sets, and the requirement names `devops-cli`.
