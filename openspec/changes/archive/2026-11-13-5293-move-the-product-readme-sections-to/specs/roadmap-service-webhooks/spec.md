## MODIFIED Requirements

### Requirement: The runbook counts each answer of the route, the 429 of the rate limit included
The subsection Webhook route of `docs/CLUSTER.md` SHALL count the answers of the route with `traefik_router_requests_total`, which Traefik counts before the middlewares of the router, so that the count includes each HTTP 429 of the rate limit.

#### Scenario: An operator counts the answers of the route
- **WHEN** an operator reads the query of the subsection Webhook route in `docs/CLUSTER.md`
- **THEN** the query is `sum by (code) (increase(traefik_router_requests_total{service="devops-roadmap-service-8000@kubernetes"}[15m]))`
- **AND** the service in the query is the backend of the Ingress `devops/roadmap-service`, as `<namespace>-<name>-<port>@kubernetes`
