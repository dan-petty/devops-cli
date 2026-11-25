# Design

## Decisions

- **Rename `Only the roadmap Service calls the pod` to `Only the roadmap Service and stage Jobs call the pod`**: The old title states that only the roadmap Service calls the pod, which contradicts the requirement body after #5483 (`k8s/devops/searxng/networkpolicy-client.yaml:32`).
- **Keep both scenarios under the modified requirement**: Keep `Another pod may call the service` (naming the roadmap-service pods, the stage Job pods, `searxng-clients`, and `searxng-stage-clients`) and `The monitoring namespace reaches the scrape port` so no base coverage is lost (`openspec/specs/searxng-service/spec.md:41-47`).
- **Update the living spec only via `openspec archive`**: `CONTEXT.md` reserves `openspec/specs/` updates for archiving a spec delta rather than direct hand edits.

## Rejected alternatives

- **Keep the old requirement heading `Only the roadmap Service calls the pod`**: Rejected, because `openspec/specs/searxng-service/spec.md:38` would continue claiming that only one client calls SearXNG while its body allows both `roadmap-service` and `roadmap-stage`.
- **Edit `openspec/specs/searxng-service/spec.md` without an OpenSpec delta**: Rejected, because direct spec edits bypass `openspec archive` and spec-delta review history.
