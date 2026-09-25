# Task 556: Defect Template Well-Formedness Check as a Command

**Issue**: [#556](https://github.com/dan-petty/devops-cli/issues/556)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

The synthetic defect corpus generator mutates source files to measure reviewer recall, but previously lacked an automated verification sweep to ensure every candidate site produces syntactically valid code and avoids comment collisions across all sample repositories.

This task implements the defect template well-formedness sweep as a standalone command and automated gate, verifying that every mutation remains valid code according to language syntax checkers, never collides with block comments or docstrings, honestly reports missing external checkers as `NOT_RUN` rather than passing, and records runs in the evaluation run store (`Mechanism.TEMPLATE_SWEEP`) for comparison and regression gating.

### Key Deliverables Completed:

- [x] **Language Syntax Checkers & Comment Collision Detection** (`devops_cli/ai/review/template_sweep.py`):
  - Multi-language syntax dispatch for Python (`ast.parse`), C (`gcc`), C++ (`g++`), JavaScript (`node`), Shell (`bash -n`), HCL (`python-hcl2`), YAML (`PyYAML`), and polyglot Tree-Sitter grammar verification.
  - Transparent status reporting: `PASS`, `FAIL`, or `NOT_RUN` (when external compilers/checkers are uninstalled), strictly preventing false passes.
  - `is_inside_comment` detection identifying collisions with line comments (`//`, `#`, `--`, `<!--`) and multi-line block comments (`/* ... */`).
  - Safe mutation application and verification pipeline decomposed into single-responsibility helpers adhering strictly to $M \le 10$ and depth $\le 5$ complexity limits.
- [x] **Run Store Persistence & Regression Gate** (`devops_cli/ai/run_store.py`):
  - Registered `Mechanism.TEMPLATE_SWEEP = "template-sweep"` in evaluation run store.
  - Metric extraction for `total_sites`, `parse_failures`, `comment_collisions`, `tested_mutations`, and `untested_sites`.
  - Regression check integration in `check_regression` ensuring `parse_failures` and `comment_collisions` remain strictly zero.
- [x] **CLI Command Surface** (`devops_cli/commands/review.py`):
  - `devops review templates list`: inspects all registered defect templates, descriptions, and supported categories.
  - `devops review templates check` (alias `sweep`): executes candidate site sweeping over sample repositories with `--samples-dir`, `--template`, `--save-run`, and `--format (table|json)`.
  - Non-zero exit code (code 1) when any syntax error or comment collision is detected.
- [x] **Automated Tests & Quality Gates** (`tests/test_review_template_sweep.py`):
  - Multi-language syntax validator tests (valid, invalid, missing tools).
  - Comment collision detection unit tests.
  - End-to-end template sweep execution on synthetic and sample fixtures.
  - Run store persistence and regression gating verification.
  - CLI command invocation and JSON serialization tests with structural tuple equality assertions.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
