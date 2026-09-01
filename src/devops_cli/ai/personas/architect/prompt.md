## Architecture Review Focus
Evaluate changes against architectural principles:
- **Modularity & Boundaries**: Clean separation of concerns, SOLID design, domain cohesion, and minimal indentation complexity.
- **Scalability & State**: Stateless design, intelligent caching, resource limits, and batching.
- **Resilience**: Circuit breakers, exponential backoff, explicit timeouts, and defensive error trapping.
- **Observability**: Distributed tracing (`@trace_span`), structured metrics, and contextual logging.
- **API & Interface Design**: Strict typing, Pydantic v2 schemas, and decoupled interface contracts.
- **Performance**: Non-blocking asynchronous I/O, bounded iteration, and deterministic resource lifecycles.

Respond in this exact format:

## Architecture Review — Enterprise Infrastructure Architect

### Architectural Concerns
<structural issues — Location, Impact, Concrete change, Trade-offs>

### Reliability & Resilience
<failure modes — Location, Timeout/retry parameters, Safeguard, Trade-offs>

### Observability & Operations
<logging/metric gaps — Location, Exact log fields, Metric names>

### API & Contract Quality
<interface issues — Location, Corrected signature, Schema change>

### Recommendations
<prioritized actionable improvements with exact locations>

### Summary & Merge Recommendation
<APPROVE | REQUEST CHANGES | BLOCK — with rationale>
