# Proposal: #4518

## Why

#4518: the LiteLLM gateway sends no spans. Its config has `callbacks: ["prometheus"]` only, and its Deployment sets no `OTEL_*` variable, so Tempo has no gateway service. The time that a call waits in the gateway queue, and the time of its retries and fallbacks, is not visible in a trace.

The LiteLLM `otel` callback writes key data on each span, also with message logging off: the key hash, the key alias, the user, the team and the `x-` headers of the request. A refused key puts its SHA-256 hash in the error text. By the owner decision of 2026-11-11 ("apply best practices"), the change uses defence in depth: content off in the gateway, and a delete rule in the Collector before Tempo.

## What Changes

- `k8s/llm/gateway/config.yaml`: `callbacks: ["prometheus", "otel"]` and `turn_off_message_logging: true`.
- `k8s/llm/gateway/deployment.yaml`: `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`, `OTEL_EXPORTER_OTLP_ENDPOINT` set to the Collector Service on port 4318, and `OTEL_SERVICE_NAME=llm-gateway`. LiteLLM metrics and events stay off (their defaults).
- `k8s/llm/gateway/networkpolicy.yaml`: one egress rule to the Collector pods of namespace `otel` on TCP 4318. The rule names the pods, so no span goes to Tempo past the Collector.
- `k8s/otel/values.yaml`: processor `transform/key_data` in the traces pipeline, between `memory_limiter` and `batch`. It deletes `metadata.user_api_key_*`, `metadata.requester_custom_headers` and each attribute whose name holds `authorization` or `api-key`, from spans and span events of all services. It replaces each 64-digit hex value in gateway spans and events. The comment on `service:` names the real Service.
- Checks of the `k8s` row of `devops ci`: the callback and the endpoint (derived from the Argo CD Application of the Collector), the egress rule, and the effect of the processor statements on the attributes that LiteLLM writes. The egress test of the gateway admits the Collector peer.
- `k8s/README.md`: a "Gateway spans" section.

The change alters manifests, so it carries a spec delta.

A gateway span becomes the child of a devops-cli span only when the request carries `traceparent`. This change ships alone: it does not depend on the client change of #2536.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `llm-telemetry-content`: two ADDED requirements, for the gateway span export and for the Collector delete rule.

## Impact

- Files: `k8s/llm/gateway/config.yaml`, `k8s/llm/gateway/deployment.yaml`, `k8s/llm/gateway/networkpolicy.yaml`, `k8s/otel/values.yaml`, `k8s/README.md`, `tests/gate/k8s_checks/llm_gateway.py`, `tests/gate/k8s_checks/otel_collector.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`.
- After the merge, Argo CD syncs the `otel-collector` and `llm` Applications. The Collector pod restarts on its new config. The gateway ConfigMap gets a new hash, so the gateway pod rolls.

## Feasibility

Read on 2026-11-11.

- Live state (`kubectl`, names only): the gateway image is `ghcr.io/berriai/litellm:v1.103.10` with no `OTEL_*` variable. The Collector image is `otel/opentelemetry-collector-contrib:0.161.0`. Namespace `otel` has the Services `otel-collector-opentelemetry-collector`, `tempo` and `tempo-headless`. The Collector pod has the labels `app.kubernetes.io/name=opentelemetry-collector` and `app.kubernetes.io/instance=otel-collector`.
- LiteLLM source at tag v1.103.10 (`b3287e39`): `litellm/integrations/opentelemetry.py` reads `OTEL_EXPORTER_OTLP_PROTOCOL` and `OTEL_EXPORTER_OTLP_ENDPOINT`, maps `http/protobuf` to the OTLP/HTTP exporter, and adds `/v1/traces` to the endpoint. `_resolve_capture_mode` returns `NO_CONTENT` when `litellm.turn_off_message_logging` is true, and `NO_CONTENT` skips the messages, the tool definitions and the raw request span. `set_attributes` writes each key of `standard_logging_payload["metadata"]` as `metadata.<key>`; `StandardLoggingUserAPIKeyMetadata` (`litellm/types/utils.py`) holds `user_api_key_hash`, `_alias`, `_user_id`, `_user_email`, `_team_id`, `_org_id`, `_end_user_id` and `_auth_metadata`, and `StandardLoggingMetadata` adds `requester_custom_headers`. `litellm/proxy/auth/user_api_key_auth.py` writes "Key Hash (Token) =<hash>" in the error of a refused key, and `async_post_call_failure_hook` puts that text in the `exception` attribute and `record_exception` in an event. Metrics and events export stay off unless `LITELLM_OTEL_INTEGRATION_ENABLE_METRICS` or `_EVENTS` is `true`. The image installs extra `proxy-runtime`, which holds `opentelemetry-exporter-otlp==1.45.1` (`pyproject.toml`, `Dockerfile`).
- LiteLLM documentation (https://docs.litellm.ai/docs/observability/opentelemetry_integration): "`litellm.turn_off_message_logging=True` forces `NO_CONTENT`", "request metadata will still be logged", "LiteLLM emits `metadata.user_api_key_*` attributes (key hash, key alias, org ID, user ID, team ID)", and "LiteLLM honors the W3C Trace Context header".
- Collector documentation at contrib v0.161.0: `processor/transformprocessor/README.md` (contexts `span` and `spanevent`, `error_mode`, context inference) and `pkg/ottl/ottlfuncs/README.md` (`delete_matching_keys`, `replace_all_patterns`).
- `otelcol-contrib validate` of image 0.161.0 accepts the rendered `config` of `k8s/otel/values.yaml`, and refuses a copy with an unknown OTTL function. A throwaway Collector of the same image, with the processor and a `debug` exporter, got one gateway span and one devops-cli span over OTLP/JSON. It exported the gateway span without the key attributes, with `<redacted>` in place of the hash in the `exception` attribute and in the event, and the devops-cli span unchanged.
- Tempo span attribute names (`list_tempo_attribute_names`, scope `span`): no current attribute name holds `authorization`, `api_key`, `api-key` or `metadata.`, so the key rules for all services delete no current attribute.

## Existing Tool Considered

The LiteLLM `otel` callback, built into the gateway image, and the `transform` processor of the OpenTelemetry Collector contrib image that runs now. No code is built and no internal code is deleted. The gate checks read committed files only.
