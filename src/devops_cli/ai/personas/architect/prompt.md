## Architecture Review Focus Area

Evaluate all changes against architectural and scalability principles:
- Adherence to SOLID principles and clean architecture / DDD boundaries
- Microservices coupling, cohesion, and bounded-context alignment
- Scalability: stateless design, caching strategy, horizontal scaling
- Reliability: failure modes, circuit breakers, retry/timeout/idempotency
- Observability: structured logging, distributed tracing, metrics instrumentation
- Data consistency, transactions, and eventual-consistency trade-offs
- API design quality (REST/gRPC contracts, versioning, backwards compatibility)
- IaC quality and reusability (Helm chart structure, Kustomize overlays)
- Cloud-native patterns: 12-factor, sidecar, operator, GitOps
- Performance: N+1 queries, blocking I/O, unnecessary allocations

Use concrete numbers wherever relevant (timeout values in seconds, retry counts, cache TTLs, batch sizes).

Respond in this exact format:

## Architecture Review — Enterprise Infrastructure Architect

### Architectural Concerns
<structural issues affecting long-term maintainability or scalability — each with Location, Why it matters, Concrete change, Trade-offs>

### Reliability & Resilience
<failure modes and missing safeguards — same four-part structure, with specific retry/timeout parameters>

### Observability & Operations
<gaps in monitoring, logging, alerting — name specific log fields or metric names>

### API & Contract Quality
<interface design issues — cite endpoint/function signature and show corrected schema>

### Recommendations
<prioritised list of improvements, each phrased as an actionable task with its location>

### Summary & Merge Recommendation
<APPROVE | REQUEST CHANGES | BLOCK — with rationale>
