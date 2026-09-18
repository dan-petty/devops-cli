# Task 250: Remediate Markdown Formatting Issues and Unbalanced Code Blocks in Review Reports

**Issue**: [#250](https://github.com/dan-petty/devops-cli/issues/250)
**PR**: None (Draft pending)
**Status**: In Progress
**Milestone**: `v0.2.20`
**Priority**: `priority/p1-high`
**Scope**: `scope/review`, `scope/ai`

---

## 1. Description & Objectives

Investigation of `review.md` reports across `.data/reviews` revealed critical Markdown formatting bugs that break report rendering in GitHub, VSCode Markdown preview, and documentation viewers:
1. **Unbalanced Code Blocks in Fix Recommendations**: In `src/devops_cli/ai/review/pipeline.py`, `f.fix` is unconditionally wrapped in triple backticks (```\n{f.fix}\n```). When `f.fix` already contains fenced code blocks or markdown, this leaves an unclosed code block (odd number of fences) swallowing all subsequent sections (detailed findings, external dependencies table, network references table) into an unclosed code block.
2. **Broken Pattern Themes & Dangling Brackets in Executive Summary**: In `src/devops_cli/ai/review/stages/reporting.py`, `_derive_finding_theme` splits naively on `[:\-\(]`, slicing inside scanner tags (e.g. `[DRY-RUN]`, `[GITLEAKS:simulated-secret]`, `[B602]`) or CLI flags (e.g. `--allow-blocked-state`), producing unclosed brackets (`**[DRY**:`) and unclosed backticks.
3. **Inline Backtick Collisions**: Blindly wrapping `rep.title` in backticks when `rep.title` already contains inline code backticks results in broken nested backticks.
4. **Markdown Asterisk Collisions**: Raw Python parameters (e.g. `**kwargs`) in findings collide with bold markdown syntax (`****kwargs****`).

#### Key Deliverables:
1. **Safe Code Block & Fix Formatting (`src/devops_cli/ai/review/pipeline.py`)**:
   - Inspect `f.fix` content: if already fenced or containing code blocks, format cleanly without double-fencing or use safe outer fences ($N+1$ backticks).
   - Ensure all code blocks opened in markdown reports are strictly closed with balanced fences.
2. **Robust Theme Derivation (`src/devops_cli/ai/review/stages/reporting.py`)**:
   - Strip leading scanner bracket tags (`[TAG:...]`, `[TAG]`) cleanly rather than splitting across internal punctuation.
   - Guard against splitting words on hyphens or colons inside identifiers, backticks, or bracketed expressions.
   - Ensure `theme` contains no unclosed brackets, backticks, or formatting tokens.
3. **Collision-Free Markdown Summary Formatting**:
   - Prevent backtick collisions when representative issue titles contain inline code spans.
   - Escape or sanitize markdown bold markers (`**`) inside titles and themes.
4. **Table Cell Formatting Integrity**:
   - Ensure pipes `|` and newlines are sanitized in `stages/reporting.py` table generation.
5. **Comprehensive Verification Suite (`tests/test_review_report_summary.py`)**:
   - Add unit and invariant tests verifying:
     - 100% balanced code fences (even number of fences) across all review markdown reports.
     - Zero unclosed brackets (`[` without matching `]`) inside bold headings/themes.
     - Zero unclosed backticks in table cells and executive summary lines.
     - Strict table column count consistency across all rows.
6. **Quality & Invariant Compliance**:
   - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
   - Consolidate linear assertions using structural tuple equality.
   - 100% passing across all 10 CI quality gates (`uv run devops ci`).
