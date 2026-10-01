# Task 701: IPv6 Egress CIDR Fix and Deny-Class Property Tests for Sandbox Policy

**Issue**: [#701](https://github.com/dan-petty/devops-cli/issues/701)
**Status**: In Progress
**Milestone**: `v0.2.24`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/cli`, `priority/p0-critical`

---

## 1. Description & Objectives

#### Key Deliverables:
- **Context & Rationale**: The policy boundary is a set of pure functions: `safe_resolve_subpath`, `validate_no_path_traversal` and `validate_path_parameter` (`src/devops_cli/core/paths.py:16-175`), the last guarding agent tool kwargs via `ai/ext_langchain.py:18` and `ai/agents/context.py:19`; `is_loopback_or_private_host` (`core/validation.py:81-98`); and the whitelist validators and ipBlock builders behind `devops sandbox network-policy` (`sandbox/models.py:55-215`). Tests use hand-picked inputs with no IPv6 or NUL case (`tests/test_consolidation_core_paths.py:128-171`, `tests/test_validation.py:190-216`); `hypothesis` is not a dependency. Defects found: `_resolve_public_host` and `_resolve_local_host` append `/32` to IPv6 addresses (`models.py:125,149,163,185`), so the docstring "strictly to validated whitelisted destinations" (`models.py:190`) is false; `_extract_host_or_ip` truncates IPv6 hosts (`models.py:63-65`); NUL makes `safe_resolve_subpath` raise `ValueError` past `error_cls` (`paths.py:56`); a substring `..` test rejects benign names; six metadata-name checks in five modules disagree (`core/validation.py:40,229`, `sandbox/probe.py:55`, `sandbox/models.py:84`, `telemetry/waterfall.py:127`, `ai/models/ollama.py:37`). vibes' campaign is a fixed event table with an unread seed (`lsm_gate.py:257-276`); its README accepts 0.85 containment, its pattern claims 1.0.
- **Deliverable Breakdown**:
  - [x] **PR1**: Emit each address's full-length prefix (`ipaddress.ip_network(ip).with_prefixlen`, `/128` for IPv6 and `/32` for IPv4) in `_resolve_public_host` and `_resolve_local_host`; parse bare, bracketed, URL, and CIDR IPv6 endpoints in `_extract_host_or_ip` using `urllib.parse` and `ipaddress`; update `is_non_public_ip` to support IPv6; add comprehensive regression tests in `tests/test_sandbox_networking.py` and `tests/test_validation.py`.
  - [ ] **PR2**: One metadata predicate on ollama's superset (`fd00:ec2::254`, bare `metadata`, trailing dot) at all six sites; NUL raises `error_cls`; a component-wise `part == ".."` check after one decode.
  - [ ] **PR3**: Add `hypothesis` to the dev group unless Reach Tally, Replay Gate and Hash-Seed Check for Parser Fuzzing already has, and write properties whose classes come from the oracle, not syntax.
- **Constraint**: The sibling task's CI profile runs explicit examples only, so these tests need a per-test `@settings(phases=[Phase.explicit, Phase.generate], derandomize=True)`: derandomized generation is fixed per commit, not a lucky search. A property that encodes today's behaviour, such as denying `%252e%252e/etc`, which pathlib never decodes, passes forever and finds nothing. The metadata predicate widens what five call sites deny; test each. No floor below 1.0: a deterministic predicate that allows one forbidden input has a bug.
- **Measured**: `uv run --no-sync python <scratch-dir>/probe/rewrite/p.py`: with `getaddrinfo` stubbed to one AAAA and one A record, `_resolve_public_host` returned `2606:4700::1/32`, which covers 2**96 addresses; `_extract_host_or_ip("fd00:ec2::254")` returned `fd00`. Same run: `validate_path_parameter("file_path", ...)` denied `notes..txt`, `v1..2.diff` and `a..b/c` but allowed `~/.ssh/id_rsa` and `file:///etc/passwd` with `allow_absolute=False`; `safe_resolve_subpath(base, "a\x00b")` raised `ValueError`.
- **Source**: vibes `patterns/kernel-enforced-lsm-sandbox-containment.md`, `patterns/zero-trust-sandboxing-and-observability.md`, `examples/ebpf-lsm-kernel-gate/lsm_gate.py`, `examples/ebpf-lsm-kernel-gate/README.md`, `examples/ebpf-lsm-kernel-gate/test_lsm_gate.py`, `examples/ephemeral-container-sandbox/README.md`, `observations/systems/34-ebpf-lsm-kernel-gates-and-dynamic-containment-fuzzing.md`
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
