# Design

## Context
See `proposal.md` for motivation and background.
Commands in `ai analyze`, `ai ingest`, `ai rag`, and `ai research` currently initiate external network calls to embedding servers, Qdrant vector databases, Valkey cache tiers, or Kubernetes clusters even when invoked under `--dry-run`.
We apply `@dry_run_class("request-plan")` to mutating or network-reaching operations and `@dry_run_class("no-external-request")` to purely local commands.

## Goals / Non-Goals

**Goals:**
- Provide request planning for all 16 external-calling commands in `src/devops_cli/ai/ai_plans.py`.
- Support `--dry-run` and global `--dry-run` for both human-readable and structured `--format json` output.
- Tag 5 purely local commands with `no-external-request` so the lazy proxy executes them safely.
- Remove all 21 commands from `tests/fixtures/dry_run_gaps.json`.

**Non-Goals:**
- Modifying underlying inference APIs or vector stores.
- Backwards-compatibility shims for legacy `--dry-run` echo output.

## Decisions

### 1. Pure Plan Builders in `ai_plans.py`
We add plan-building helper functions in `src/devops_cli/ai/ai_plans.py` that return `list[PlannedRequest]`.
*Rationale*: Centralizing planned request generation keeps command callbacks clean and ensures unit tests can verify plan generation offline.
*Alternative considered*: Inlining plan creation inside each command callback. Rejected because it duplicates request construction logic and bloats Typer command handlers.

### 2. Handling Ingestion and RAG Serialization
For commands that support `--format json` or `--json` (e.g. `ai rag query`, `ai ingest docs`), a dry-run execution returns the schema-compliant model instance with `requests` attached, or an empty result model marked with `dry_run=True`.
*Rationale*: Consistent with the owner's rule: return the same response type as real calls with planned requests attached.

## Risks / Trade-offs
- [Risk] Some commands have conditional branching based on remote resource state (e.g. Qdrant collection exists vs missing).
  → Mitigation: In dry-run mode, construct requests representing the primary nominal workflow without reaching out to probe server health.
