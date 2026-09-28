# Task 503: Synthetic Defect Templates for Application Languages

**Issue**: [#503](https://github.com/dan-petty/devops-cli/issues/503)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

The synthetic defect generator (#415) injects into Python, YAML and Dockerfiles only, so recall cannot be measured on other languages.

### Key Deliverables Completed:

- [x] **One template, many languages**: a template now pairs file suffixes with a finder for each
  language (`DefectTemplate.finders`), so `--template drop-bounds-check` covers every language
  it knows.
- [x] **Guards in brace languages** (TypeScript/JavaScript, Go, Rust, Java, C#, C/C++):
  - `drop-bounds-check` removes an ordering guard;
  - the new `drop-error-check` removes a guard that stops on an error or a missing value
    (`err != nil`, `== null`, `!ptr`, `is_none()`, `rc != 0`).

  Guards are found on code with literals and comments blanked, so braces inside strings are not
  counted. A guard is removed only when:
  - it is a whole `if` statement filling its lines;
  - its body only exits (return, throw, panic, abort);
  - no `else` follows;
  - it is not the body of a braceless `if` or loop;
  - for Go, it has no init statement and `err` is read again later, or Go would not compile.

  Braces may open on the `if` line or the next (Allman style, common in C#). A report counts
  from the enclosing function's start to ten lines past the guard, like Python's.
- [x] **Dropped awaits** in TypeScript/JavaScript and C#. `for await` and `await foreach` or
  `await using` are left alone.
- [x] **Disabled TLS verification**:
  - TypeScript/JavaScript: `rejectUnauthorized`, or a new `https.Agent`;
  - Go: `InsecureSkipVerify`, or a new `tls.Config`;
  - Rust: `danger_accept_invalid_certs`, or a new reqwest `Client::builder()`;
  - C#: an accept-any certificate callback on a new `HttpClientHandler`.
- [x] **Widened file modes**:
  - the mode argument of `MkdirAll`, `WriteFile`, `OpenFile`, `mkdir`, `open`, `chmod` and the
    Node `*Sync` calls;
  - `mode:` options and Rust `mode()` / `from_mode()`;
  - Java `PosixFilePermissions.fromString`.
- [x] **C/C++ unbounded string calls** (`unbounded-string-copy`): `strncpy`, `strncat`,
  `snprintf` and `vsnprintf` lose their size argument.
- [x] **Documentation**: the template table in `docs/SELF_IMPROVEMENT.md` lists each template's
  languages. It no longer says review pages lack line numbers, which #499 fixed.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_defects_languages.py`:
    - one guard per language removed whole, with its region and evidence;
    - 12 places that must be skipped (a body that does more than exit, `else`, `else if`, a
      braceless loop body, a string, Go without a later `err` read, an init statement, a
      braceless multi-line guard, `for await`, `await foreach`, a multi-line call, TLS already
      off);
    - 15 one-line defects across the languages;
    - a mixed-language corpus.
  - The existing template tests moved to per-language finders.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on the Pinned Samples (#502)

Every site of every template was applied to the application samples, one at a time, and the
mutated file checked:

| Sample | Sites | Check | Result |
| :--- | ---: | :--- | :--- |
| cJSON (C) | 145 | `gcc -fsyntax-only` | all compile |
| express (JavaScript) | 9 | `node --check` | all parse |
| fmt (C++) | 77 | `g++ -std=c++20 -fsyntax-only`, every header included | 76 compile; one fails fmt's compile-time format-string check |
| ky, cobra, serde_json, gson, serilog | 282 | tree-sitter, errors before and after | no new errors, except one site in a serilog file tree-sitter already misparses (310 errors) |

The fmt failure removes `if (num_digits <= digits10) return int(value);` from a `constexpr`
parser. The code is well formed. The dropped fast path makes `consteval` format-string checking
reject `{:08x}`, so that defect shows up when the code is compiled.

`devops review corpus generate` over the eight application samples injected 91 defects:
- 30 `drop-bounds-check`;
- 44 `drop-error-check`;
- 13 `drop-await`;
- 4 `unpin-action-ref` in the samples' workflow files.

None of the samples configures TLS, writes files with explicit modes or calls bounded C string
functions, so those templates are exercised by the unit tests only.

The project does not install `tree_sitter`. The AST engine, which maps TypeScript, Go, Rust, Java
and HCL with tree-sitter, falls back to its regex parser on every file. That is for #505 to record
and #506 to fix.
