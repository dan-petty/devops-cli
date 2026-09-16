# Task 118: High-Performance AST Context Packer with Binary Search Truncation

**Issue**: [#118](https://github.com/dan-petty/devops-cli/issues/118)
**PR**: [#224](https://github.com/dan-petty/devops-cli/pull/224)
**Status**: In Review
**Milestone**: `v0.2.19`
**Priority**: `priority/p1-high`
**Scope**: `scope/ai`

---

## 1. Description & Objectives

DevSecOps review identified an $O(N^2)$ algorithm in `_prune_tree_to_budget` ([`src/devops_cli/ai/context_packer.py`](file:///workspaces/devops-cli/src/devops_cli/ai/context_packer.py)) that repeatedly executed `ast.unparse(tree)` and `count_tokens` inside a while-loop for every statement popped, incurring excessive CPU and latency overhead when pruning large modules (>300ms–1000ms for 500–1000 statements).

#### Key Deliverables:
1. **Per-Statement Token Weight Memoization**:
   - `_estimate_stmt_tokens(stmt: ast.stmt) -> int` evaluates signature complexity in $O(1)$ time without AST unparsing.
   - Memoize token weight on AST node (`_est_tokens`) to prevent redundant computation.
2. **Binary Search Truncation Index Discovery**:
   - Compute prefix sums of token weight estimates.
   - Use `bisect_right` to pinpoint the approximate statement cutoff boundary in $O(\log N)$ time.
   - Execute localized binary search with `ast.unparse` around the boundary to guarantee strict token budget compliance without linear re-unparsing.
3. **Sub-10ms Runtime on 1,000-Statement AST Trees**:
   - Reduce unparsing overhead to $\le 4$ operations total.
   - Warm up tokenizer encoding in `ContextPacker` initialization.
4. **Architectural Invariants & Quality Gates**:
   - Cyclomatic complexity $\le 10$ and nesting depth $\le 5$ across all functions.
   - 100% passing across all 10 CI quality gates (`uv run devops ci`).
