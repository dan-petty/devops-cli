# Task: Optimize Caching Configuration Across All GitHub Workflows (#99)

**Issue**: #99
**PR**: #100
**Status**: Done
**Milestone**: v0.2.15
**Priority**: priority/p2-medium
**Scope**: scope/ci

## Description
Optimize caching configurations across GitHub Actions workflows (`ci.yml` and `release.yml`) to reduce workflow execution latency, eliminate redundant runtime toolchain fetching, prevent unbounded cache growth, and speed up container builds.

## Deliverables
- [x] Optimize Caching Configuration Across All GitHub Workflows (P2 - Medium, PR #100 - Merged)
- [x] Configure `cache-python: "true"` and `prune-cache: "true"` in `astral-sh/setup-uv`.
- [x] Add explicit `cache-dependency-glob: "uv.lock"` for deterministic cache invalidation.
- [x] Add SHA-pinned `actions/cache` step in `ci.yml` for mypy, ruff, and pytest caches.
- [x] Add `cacheFrom` layer reuse to DevContainer CI build steps.
- [x] Author declarative test contract in `tests/test_ci.py` (18/18 passing).
