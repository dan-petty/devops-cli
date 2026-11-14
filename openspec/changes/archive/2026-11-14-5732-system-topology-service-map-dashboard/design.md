# Design

## Decisions
- Dedicated Dashboard:
  - Create `system-topology.json` with uid `system-topology` and title `System Topology & Service Map`.
  - Add to a separate ConfigMap `grafana-topology-dashboards` to stay below kubectl annotation size limits.
- Panel Layout:
  - Row 1: `Network & Ingress Topology` (`id: 1, y: 0, w: 24, h: 1`).
    - Panel 2: `Ingress Traffic by Entrypoint` (`id: 2, y: 1, w: 12, h: 8, x: 0`). PromQL: `sum by (entrypoint, protocol) (rate(traefik_entrypoint_requests_total[5m]))`.
    - Panel 3: `Router to Service Routing Rate` (`id: 3, y: 1, w: 12, h: 8, x: 12`). PromQL: `sum by (router, service) (rate(traefik_router_requests_total[5m]))`.
  - Row 4: `Distributed Trace Service Map` (`id: 4, y: 9, w: 24, h: 1`).
    - Panel 5: `Service Dependency & Call Graph` (`id: 5, y: 10, w: 24, h: 12, x: 0`, type: `nodeGraph`).
      - Datasource: `{"type": "tempo", "uid": "tempo"}`.
      - Target: `{"datasource": {"type": "tempo", "uid": "tempo"}, "queryType": "serviceMap", "expr": "serviceMap", "refId": "A"}`.
  - Row 6: `Project Brain & Decision Flow` (`id: 6, y: 22, w: 24, h: 1`).
    - Panel 7: `Decision Point Resolution Rate` (`id: 7, y: 23, w: 12, h: 8, x: 0`). PromQL: `sum by (point, resolver, band) (rate(devops_cli_decision_point_total[5m]))`.
    - Panel 8: `RAG Latency & Embedding Cache Hit Rate` (`id: 8, y: 23, w: 12, h: 8, x: 12`). PromQL:
      - Ref A: `histogram_quantile(0.95, sum by (stage) (rate(devops_cli_rag_query_duration_ms_bucket[5m])))`
      - Ref B: `sum(rate(devops_cli_embedding_cache_lookups_total{result="hit"}[5m])) / clamp_min(sum(rate(devops_cli_embedding_cache_lookups_total[5m])), 0.001) * 100`

## Rejected alternatives
- Adding panels to `llm-stack.json`: Rejected because `llm-stack.json` focuses specifically on GPU resources and model inferences.
- Standalone HTML graph: Rejected because Grafana provides built-in Node Graph panel integration with live trace data.
