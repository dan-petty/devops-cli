# Proposal: #4539

## Why

#4539: the processor `transform/key_data` of the Collector (#4518) does not delete the request and response bodies of LiteLLM management endpoint spans. On `/key/block` and `/key/unblock`, `request.key` can hold a raw `sk-` virtual key. On `/team/{team_id}/callback`, `request.callback_vars` holds callback secrets, and `response.data` holds the team row with these secrets. Thus Tempo can store key data from the gateway. The path is latent: Tempo has no `request.*` or `response.*` span attribute now, but an operator call to `/key/block` or a team callback set-up writes the data.

## What Changes

- `k8s/otel/values.yaml`: one span statement in `transform/key_data`, `delete_matching_keys(span.attributes, "^(request|response)[.]")`, with the condition `service.name == "llm-gateway"`. It deletes the management bodies by prefix, not field by field, so a new body field is also deleted. The comment of the processor names the management hooks.
- `tests/gate/k8s_checks/otel_collector.py`: `request.key`, `request.callback_vars` and `response.data` in `GATEWAY_KEY_ATTRIBUTES`, so the `k8s` row of `devops ci` fails if the path comes back.
- `k8s/README.md`: the "Gateway spans" section names the `request.*` and `response.*` attributes of management spans.
- `openspec/specs/llm-telemetry-content/spec.md`: the requirement "The Collector deletes gateway key data before Tempo" also covers `request.*` and `response.*` attributes of gateway spans.

The change alters a manifest, so it carries a spec delta.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `llm-telemetry-content`: the MODIFIED requirement "The Collector deletes gateway key data before Tempo".

## Impact

- Files: `k8s/otel/values.yaml`, `k8s/README.md`, `tests/gate/k8s_checks/otel_collector.py`.
- After the merge, Argo CD syncs the `otel-collector` Application and the Collector pod restarts on its new config. Only the Collector changes, so no rollout order is necessary.

## Feasibility

Read on 2026-11-11.

- LiteLLM source v1.103.10 (the image tag in `k8s/llm/gateway/deployment.yaml`, from the uv cache): `_emit_management_endpoint_otel_span` (`litellm/proxy/management_helpers/utils.py`) reads the parsed request body when the endpoint has an `http_request` argument, and `_CREDENTIAL_FIELDS` filters only the top-level response fields. `async_management_endpoint_success_hook` and `_failure_hook` (`litellm/integrations/opentelemetry.py`, lines 3390, 3399 and 3448) write `request.<field>` and `response.<field>`. `add_team_callbacks` returns `{"status": "success", "data": <team row>}`.
- A search of the LiteLLM package for each attribute key that starts with `request.` or `response.` (string literals, f-strings and prefix arguments) finds these three lines only. Thus the rule removes no model, route, token or error attribute.
- Tempo span attribute names (`list_tempo_attribute_names`, scope `span`, 2026-11-11): no name starts with `request.` or `response.`.
- `otelcol-contrib validate` of image `otel/opentelemetry-collector-contrib:0.161.0` (the live version) accepts the rendered `config` of `k8s/otel/values.yaml`. A copy with an unknown function in the new statement fails, so validate parses the statement.
- A throwaway Collector of the same image, with the processor and a `debug` exporter, got a `/key/block` span of `llm-gateway` over OTLP/JSON. It exported the span without `request.key`, `request.callback_vars` and `response.data`, with the route, model, token and error class attributes. A devops-cli span kept its `request.id`. The same Collector without the new statement exported the three key attributes.
- The `k8s` row of `devops ci` fails on the base with the new key attributes, and passes with the statement.

## Existing Tool Considered

The `transform` processor and the OTTL function `delete_matching_keys` of the OpenTelemetry Collector contrib image that runs now. No code is built and no internal code is deleted.
