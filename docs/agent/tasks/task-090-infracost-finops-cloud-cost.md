# Task: Infracost FinOps Cloud Cost Engine (#90)

**Issue**: #90
**PR**: #97
**Status**: Done
**Milestone**: v0.2.15
**Priority**: priority/p1-high
**Scope**: scope/tf

## Description
Infracost FinOps cloud cost analysis, resource-level breakdown, diff calculation, budget guardrail validation, and FastMCP integration for Terraform stacks.

## Deliverables
- [x] Infracost FinOps Cloud Cost Engine (`devops tf cost`) (P1 - High, PR #97 - Merged)
- [x] Pydantic models `TFCostResource` and `TFCostBreakdownResult` in `src/devops_cli/models/tf.py`.
- [x] Infracost FinOps engine in `src/devops_cli/tf/cost.py` (breakdown, diff, budget validation, offline mock).
- [x] Added `cost breakdown` and `cost diff` commands to `src/devops_cli/commands/tf.py`.
- [x] Exposed `tf_cost_estimate` FastMCP tool in `src/devops_cli/ai/mcp/server.py`.
- [x] Unit tests and invariant verification in `tests/test_tf_cost.py` (20/20 passing).
