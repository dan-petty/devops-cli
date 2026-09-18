## Architecture Review Focus
Evaluate changes against core architectural principles:
- **Modularity & Boundaries**: Clean separation of concerns, SOLID design, domain cohesion, low coupling, and minimal nesting complexity.
- **Code Clarity & Clean Solutions**: Decompose procedural dispatchers and complex branching into table lookups or single-responsibility helpers. Eliminate dead code, vestigial fallback shims, and legacy workarounds.
- **Scalability & State**: Stateless design where appropriate, intelligent caching, resource limits, and batching.
- **Resilience**: Circuit breakers, exponential backoff, bounded timeouts, and defensive error trapping.
- **Observability**: Distributed tracing, structured metrics, and contextual logging.
- **API & Interface Design**: Explicit typing, clear data contracts, decoupled interface boundaries, and backwards compatibility.
- **Target Runtime Idioms**: Support target runtime idioms without reporting modern syntax features as syntax errors.
- **Performance**: Non-blocking asynchronous I/O, bounded iteration, and deterministic resource lifecycles.
- **Disproof & Anti-Hallucination**: Dismiss theoretical warnings on abstract mixins, interfaces, or base classes legitimately implemented by subclasses.
