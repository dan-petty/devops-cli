# Task 506: AST Support for C#, C/C++, Shell and Markdown

**Issue**: [#506](https://github.com/dan-petty/devops-cli/issues/506)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

The AST engine maps Python, TypeScript, JavaScript, Go, Rust, Java and HCL. C#, C, C++, shell and Markdown files yield no symbols, so repomaps, context packing and review grounding see nothing in them.

#### Key Deliverables:
- Tree-sitter grammars where a maintained package exists, and fallback extractors for functions, types and headings, each tested on its pinned sample repository.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
