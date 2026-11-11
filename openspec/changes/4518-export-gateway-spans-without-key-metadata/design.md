# Design

## Decisions

- **Two layers.** The gateway turns off message content with `turn_off_message_logging`, the setting that overrides every other content setting of LiteLLM. The Collector deletes key data, because LiteLLM writes it with content off. A later LiteLLM release, or a changed header, cannot send key data to Tempo past the Collector.
- **One `transform` processor.** OTTL acts on span attributes and on span event attributes, and the exception event of a refused key holds the hash. The `attributes` processor acts on span attributes only.
- **Two statement groups, `span` and `spanevent`.** Context inference puts a group with both paths in the `spanevent` context, which runs once for each event, so a span with no event would keep its key attributes.
- **Key-name rules for all services, the hash rule for the gateway only.** No devops-cli span holds an attribute whose name holds `metadata.`, `authorization` or `api-key` (Tempo attribute names). devops-cli spans can hold 64-digit hex digests, which are not keys.
- **`error_mode: propagate`.** A statement that fails drops the batch, so no span leaves with key data. The statements act on maps and strings only, so a failure is not expected.
- **Endpoint by Service DNS, egress by Collector pod labels.** The gateway uses the same Service name as the devops-cli config, and the rule admits only the Collector pods, so no gateway span reaches Tempo directly.
- **OTLP/HTTP with `http/protobuf`.** The LiteLLM HTTP exporter sends protobuf for each of `otlp_http`, `http/protobuf` and `http/json`; `http/protobuf` names what goes on the wire.
- **The check applies the statements.** A check of the `k8s` row reads the two OTTL functions of the processor, applies them to the attributes that LiteLLM v1.103.10 writes, and fails on any other statement. Go RE2 and Python `re` read the patterns of the rule in the same way: they use no look-around and no back-reference.

## Rejected alternatives

- **Content off alone.** Rejected: the LiteLLM page says that "request metadata will still be logged", and the source writes the key hash and alias with content off.
- **Delete `metadata.*` entirely.** Rejected: `metadata.user_agent`, `metadata.team_id` and the routing data help a trace and hold no key.
- **The `redaction` processor.** Rejected: it masks by an allow list of keys, so each new LiteLLM attribute would need an entry, and the rule needs deletes by name pattern.
- **A gRPC exporter (4317).** Rejected: the gateway policy and the devops perimeter open OTLP/HTTP only, and the client sends no gRPC.
- **A real Collector in the `k8s` row.** Rejected: the row runs on the stock runner with no container image pull. The validate run and the throwaway Collector run of the feasibility section are the repeatable manual check.
