# Design: #5716

## Decisions

### 1. Set provider to custom
- Set `provider: custom` in the plugin `jsonData`.
- This selects the Custom API provider card in the Grafana interface.

### 2. Remove /v1 from the gateway URL
- Set `url: http://llm-gateway.llm.svc.cluster.local:4000`.
- The plugin Go backend automatically appends `/v1` to the configured URL.

## Rejected Alternatives
- Keep provider as openai: Rejected because the interface disables URL configuration and forces OpenAI endpoints.
