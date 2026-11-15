# Design

## Decisions
- Classify backend destinations using `is_at_or_under(host, "local")` from `dns_names` to conform to network AST rules.
- Identify loopback addresses via `ipaddress.ip_address(host).is_loopback` and `"localhost"`.
- Reject RFC 1918 private IP addresses as local; treat them as cloud backends that incur spend.
- Support `local/` prefix in `_is_local_tier` to identify local models served through the gateway.
- Map provider prefixes (`anthropic/`, `gemini/`, `openrouter/`) in `CONST_AI_GATEWAY_HOSTED_MODELS` and pricing tables.

## Rejected alternatives
- Modifying `k8s/llm/gateway/config.yaml` to duplicate model routes: Rejected because it breaks gateway render matrix tests and k8s configuration parity.
- Checking private IP addresses as local: Rejected because cloud backends running on VPC private IPs incur cost.
