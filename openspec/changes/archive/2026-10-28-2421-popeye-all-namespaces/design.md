# Design

## Context

See proposal.md - Why. `build_popeye_cmd` in `src/devops_cli/config/commands.py` builds the command-line argument list for Popeye invocations.

## Goals / Non-Goals

**Goals:**
- Include `-A` in Popeye commands when `namespace` is None or omitted, ensuring Popeye scans all cluster namespaces.
- Keep `-n <namespace>` without `-A` when `namespace` is provided.

**Non-Goals:**
- Change Popeye output parsing or finding severity mapping.
- Change command builders for other scanners.

## Decisions

### Decision 1: Add `-A` when namespace is empty or None

When `namespace` is not supplied, `build_popeye_cmd` appends `-A` to the argument list. When `namespace` is supplied, it appends `-n` and the namespace value.

**Alternatives considered:**
- *Omit `-A` and expect Popeye default behavior:* Rejected: Popeye 0.22.1 defaults to the current context namespace when `-A` is omitted.
- *Pass `-n all` for all namespaces:* Rejected: Popeye queries a literal namespace named `all` instead of scanning all namespaces.

## Risks / Trade-offs

- [RBAC requirements] → A cluster-wide scan with `-A` requires read permissions across all namespaces. This matches the documented role of cluster sanitization.

## Migration Plan

No migration needed. Pre-1.0 alpha software retains no backwards compatibility shims.
