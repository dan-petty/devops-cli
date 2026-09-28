# Task 537: Defect Generator Injects Into Code Examples Inside Block Comments

**Issue**: [#537](https://github.com/dan-petty/devops-cli/issues/537)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

The first run of `devops review samples validate --review` (#505) found 9 of 78 brace-language
injections inside multi-line comments, all `drop-await` in ky's JSDoc examples. An example is
`const text = await ky('https://example.com', options).text();` in `types/ky.ts`. The
brace-language finders (#503) blanked string literals and one-line comments, but did not track a
`/* ... */` block spanning lines. So documentation counted as code, and the corpus scored the
reviewer on defects that do not exist: 9 of the 20 TypeScript injections. The substitution
templates (TLS, file modes) matched raw lines, so a commented-out setting could also be changed.

### Key Deliverables Completed:

- [x] **Block comments spanning lines are blanked**: `_mask_lines` tracks a `/*` left open on one
  line through the line that closes it. Code after the `*/` on that line is still code. The
  masking decides first which parts of a line are strings, so a `/*` or `//` inside a string
  (`"src/**/*.ts"`, a URL) opens no comment. Guards, awaits, C string calls and the Terraform
  block tracker all see code only.
- [x] **Substitutions skip comments**: `_substitute(..., code_only=<language syntax>)` applies a
  rule only where it matches the same text once comments are blanked. Strings are kept, since
  some rules match inside them (`PosixFilePermissions.fromString("rw-------")`). This applies to
  TLS verification in TypeScript/JavaScript, Go, Rust and C#, to file modes in brace languages
  and Java, and to the Terraform public-access and encryption rules.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_defects_comments.py`: 13 cases, each naming the lines that may change.
    - Excluded: a JSDoc example, a guard in a C block comment, TLS and mode settings in one-line
      and block comments (Go, Rust, C#, Java), `strncpy` and a Terraform attribute in block
      comments.
    - Kept: code after a comment closes, `/*` inside a string, a URL.
  - 10 of them fail without the fix.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on the Pinned Samples (#502)

Every site of every template on the brace-language and Terraform samples was checked against an
independent block-comment tracker. None is inside a block comment now. The only counts that
changed are TypeScript/JavaScript:
- `drop-await`: 99 sites down to 44.
- `drop-bounds-check`: 15 down to 12. The three removed `if` statements sit in `@example` blocks
  of ky's type files.

Every other language's sites are unchanged.
