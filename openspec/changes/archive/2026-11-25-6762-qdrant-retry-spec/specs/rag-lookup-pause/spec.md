## REMOVED Requirements

### Requirement: qdrant-retry-wait-uses-clock-seam
**Reason**: Move Qdrant client retry wait rules from `rag-lookup-pause` into `qdrant-request-retry`, replace the stale `tenacity` reference with the `sleep` clock-seam parameter used by `_execute_with_retry`, and correct the three-attempt wait count to two waits (`0.5` and `1.0` seconds) (#6762).
**Migration**: See `openspec/specs/qdrant-request-retry/spec.md`.
