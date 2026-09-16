# Task 119: Polyglot Tree-Sitter File Size Boundary Guard & Resource Containment

**Issue**: [#119](https://github.com/dan-petty/devops-cli/issues/119)
**PR**: Pending
**Status**: In Progress
**Milestone**: `v0.2.19`
**Priority**: `priority/p1-high`
**Scope**: `scope/ai`

---

## 1. Description & Objectives

DevSecOps review revealed that while the Python AST parser enforces `MAX_REPOMAP_FILE_SIZE_BYTES` (5MB), `_polyglot_to_file_node` in `devops_cli.ai.repomap` parses arbitrary-sized polyglot files (TypeScript, Go, Rust, Java, HCL) without checking file size, allowing massive files, minified bundles, or generated database dumps to cause memory spikes or OOM crashes. Furthermore, circular symlinks or symlinks escaping repository workspace boundaries must be safely trapped and excluded.

#### Key Deliverables:
1. **Mandatory File Size Boundary Guard**:
   - Pre-flight verification in `_polyglot_to_file_node` against `MAX_REPOMAP_FILE_SIZE_BYTES`.
   - Structured warning log when skipping oversized polyglot or Python files.
2. **Symlink Traversal & Resource Containment**:
   - Defensively resolve `source_file` catching `(OSError, RuntimeError)` to prevent circular symlink traversal (`ELOOP`).
   - Validate that resolved file paths remain strictly contained within `base_root` (`is_relative_to`), preventing workspace boundary escapes.
3. **Comprehensive Test Suite (`tests/test_repomap.py`)**:
   - 100% test coverage across `src/devops_cli/ai/repomap.py`.
   - Specific coverage for size boundaries, circular symlinks, and escaping links.
