# Task 272: Multi-Scale Semantic Outline & Inspectional Scanner (`devops ai read --inspect`)

**Issue**: [#272](https://github.com/dan-petty/devops-cli/issues/272)
**Status**: Done
**Milestone**: `v0.2.21`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/ai`, `priority/p0-critical`

---

## 1. Description & Objectives

Replaces naive monolithic file dumping with human-like inspectional reading and hierarchical perceptual scaffolding. Allows agents to navigate code and documentation across 3 discrete focal zoom levels:

#### Key Deliverables:
- [x] 1. **Level 0 (Topology)**: AST class/method hierarchies, exported symbols, docstring summaries, and cyclomatic hotspots without function bodies (< 200 tokens/file).
- [x] 2. **Level 1 (Structural Outline)**: Function signatures, parameter types, return contracts, and control-flow sketches.
- [x] 3. **Level 2 (Deep Focal Window)**: Line-bounded targeted code slices with surrounding breadcrumb context.
- [x] 4. **High-Performance Inspection Engine**: Sub-10ms AST outline generation; 85%+ token reduction compared to full-file ingestion; seamless integration with `Stage1PreAnalysis` and `FileAnalysisMeta`.
- [x] 5. **CLI Subcommand**: Native `devops ai read <path> [--inspect] [--level 0|1|2] [--lines L1:L2] [--symbol NAME] [--format text|json|markdown]` with trailing `--dry-run`.
- [x] 6. **FastMCP Integration**: Exposed `ai_read` tool in FastMCP server for IDE coding assistants.
- [x] 7. **Comprehensive Test Suite**: Unit and integration test coverage with structural tuple equality assertions.
- [x] 8. **Architectural Invariants**: Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ enforced project-wide.

---

## 2. Verification Results

- **Gated CI Quality Gate**: `uv run devops ci` passed 100% across all quality checks.
- **Sub-10ms Generation**: Verified sub-10ms AST outline generation on representative files.
- **Token Reduction**: Verified > 85% token reduction across Level 0 and Level 1 outlines compared to full raw files.
- **Dynamic Documentation**: Regenerated `CLI_REFERENCE.md` and `MCP_TOOLS.md` via `devops docs generate --sync-readme`.
