# Task 648: Skip Cloudflare Radar Threat Intel Lookups for Local and Reserved Domains

**Issue**: [#648](https://github.com/dan-petty/devops-cli/issues/648)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/security`, `priority/p1-high`

---

## 1. Description & Objectives

During trace analysis in OpenTelemetry / Jaeger (`http://localhost:16686`), repeated `lookup.error` tags and blocked network egress attempts occurred under span `threat_intel.lookup.cloudflare`:
```
External network call blocked during test execution: attempt to connect to 104.18.31.78:443. All external APIs and endpoints must be mocked in tests.
```
These errors were triggered for internal, local, or documented test hostnames including `localhost`, `host.lan`, `node1.example.internal`, and `host.minikube.internal`.

### Root Cause
1. In `src/devops_cli/security/vulnerability_lookup.py`, `CloudflareRadarClient.check_domain` and `_partition_cached_domains` only checked `if is_example_or_invalid_domain(target):`.
2. Unlike `ShodanInternetDBClient.check_ip`, which defensive checks `not is_public_ip(ip) or is_example_or_reserved_ip(ip)`, `CloudflareRadarClient` failed to check `is_local_or_reserved_domain(target)`.
3. In `src/devops_cli/security/reference_extractor.py`, `is_example_or_invalid_domain` explicitly excludes `localhost` and `.localhost` (returning `False`), delegating `localhost` handling to `is_local_or_reserved_domain`.
4. As a result, internal homelab hostnames (`*.lan`, `*.local`, `*.internal`) and `localhost` were dispatched over public HTTP to Cloudflare Radar API (`https://api.cloudflare.com/client/v4/radar/intel/domain/<target>`), violating zero-trust egress safety, leaking internal hostnames, and failing in offline/test environments.

### Key Deliverables:
- [x] **Local/Reserved Domain Defense in CloudflareRadarClient** (`src/devops_cli/security/vulnerability_lookup.py`):
  - Import `is_local_or_reserved_domain` from `devops_cli.security.reference_extractor`.
  - Update `check_domain` and `_partition_cached_domains` to intercept both `is_example_or_invalid_domain(target)` and `is_local_or_reserved_domain(target)`.
  - Provide descriptive static `NetworkReputationRecord` for local or reserved network domains without invoking remote network queries.
- [x] **Unit & Regression Testing** (`tests/test_vulnerability_lookup.py`):
  - Add comprehensive test asserting that `localhost`, `*.lan`, `*.local`, `*.internal`, and `*.test` resolve offline via `CloudflareRadarClient` without triggering HTTP queries or mock calls.
  - Verify structural tuple equality assertions meeting $M \le 10$ cyclomatic complexity limits.
- [x] **Gated CI Compliance**:
  - 100% pass on all quality checks via `devops ci`.
