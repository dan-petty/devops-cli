# Task 122: Distributed Threat Intelligence Valkey L2 Cache & Radar Batching

**Issue**: [#122](https://github.com/dan-petty/devops-cli/issues/122)
**PR**: TBD
**Status**: In Progress
**Milestone**: `v0.2.18`
**Priority**: `priority/p1-high`
**Scope**: `scope/security`, `scope/valkey`

---

## 1. Description & Objectives

OpenTelemetry review traces revealed `threat_intel.lookup.cloudflare` called sequentially over 200 times per multi-file scan (causing 20+ seconds of aggregate latency) because `CloudflareRadarClient` in `devops_cli.security.vulnerability_lookup` only utilized an ephemeral in-memory dictionary cache on the instance.

#### Key Deliverables:
1. **Distributed Valkey L2 Cache Integration ([`vulnerability_lookup.py`](file:///workspaces/devops-cli/src/devops_cli/security/vulnerability_lookup.py))**:
   - Cache key format: `valkey:threat_intel:domain:<target>`.
   - Configurable TTL (`DEFAULT_THREAT_INTEL_CACHE_TTL_SECONDS = 86400`).
   - Graceful offline fallback when Valkey is unreachable (transparently using in-memory L1 cache).
2. **Domain Batch Lookup Pipeline ([`vulnerability_lookup.py`](file:///workspaces/devops-cli/src/devops_cli/security/vulnerability_lookup.py))**:
   - `check_domains_batch(domains: list[str]) -> dict[str, NetworkReputationRecord]`.
   - Resolves cached records in batch via Valkey L2, querying remote Cloudflare Radar only for uncached cache-miss entries.
   - Pipelined / concurrent resolution with adaptive timeout safety.
3. **Review Pipeline Integration ([`src/devops_cli/ai/review/pipeline.py`](file:///workspaces/devops-cli/src/devops_cli/ai/review/pipeline.py))**:
   - Use `check_domains_batch` for all discovered domain targets during security pre-analysis.
4. **Comprehensive Test Suite ([`tests/test_security_threat_intel.py`](file:///workspaces/devops-cli/tests/test_security_threat_intel.py))**:
   - 100% test coverage validating L2 cache hits, misses, TTL expiration, batching, offline fallback, and telemetry metrics.

---

## 2. Verification & Acceptance Criteria

- [x] 95%+ cache hit rate on repeated domain threat intelligence lookups.
- [x] Sub-millisecond lookup latency from Valkey cache (<1ms).
- [x] 100% test coverage in `tests/test_security_threat_intel.py`.
- [x] All architectural invariants and complexity gates pass ($\le 10$).
- [x] Local `uv run devops ci` passes with $\ge 90.0\%$ coverage.
- [ ] Remote CI passing and PR staged.
