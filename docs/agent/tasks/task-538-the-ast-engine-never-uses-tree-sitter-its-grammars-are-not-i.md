# Task 538: The AST Engine Never Uses Tree-Sitter: Its Grammars Are Not Installed

**Issue**: [#538](https://github.com/dan-petty/devops-cli/issues/538)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

`TreeSitterEngine` maps TypeScript, JavaScript, Go, Rust, Java and HCL with tree-sitter, but
neither `tree_sitter` nor any grammar was a dependency. The first sample validation (#505) found
every file read by the regex fallback. In the pinned samples, 16 of 31 TypeScript, 10 of 37 Rust,
8 of 85 Java and 1 of 5 HCL files yielded no symbols, so repository maps, context packing and
review grounding saw only what the regex found.

### Key Deliverables Completed:

- [x] **Dependencies**: `tree-sitter` and the official grammars: `tree-sitter-python`,
  `-typescript`, `-javascript`, `-go`, `-rust`, `-java`, and `tree-sitter-hcl` from the
  tree-sitter-grammars organisation.
- [x] **Grammars load by their entry points**:
  - `LANG_TO_GRAMMAR` pairs each language with its package and entry point.
  - The TypeScript package's `language_typescript` and `language_tsx` are separate grammars, so
    `.tsx` files get the JSX-aware one. `grammar_mod.language()` did not exist for TypeScript,
    and loading failed silently.
- [x] **Declarations the native walk missed are named**:
  - TS/JS: arrow and function-expression declarators (`const f = () => ...`), type aliases,
    enums and abstract classes;
  - Go: type specs as struct, interface or type;
  - Rust: enums, type aliases, unions, modules, constants, statics and `macro_rules!`;
  - Java: enums, records, constructors, annotation types and their elements;
  - HCL: top-level blocks, named as the fallback names them (`resource "aws_vpc" "this"`),
    nested blocks excluded.
- [x] **Accurate parser reporting**: a file tree-sitter parses with no symbols, and the fallback
  finds none either (a `package-info.java`), is reported as parsed by tree-sitter.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_treesitter_native_symbols.py`: each language parsed natively with every new
    declaration kind; TSX; nested Terraform blocks excluded; a file declaring nothing.
  - `tests/test_treesitter_engine.py`: `.tsx` detects as `tsx`.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on the Pinned Samples (#502)

`devops review samples validate`, before and after:

| Category | Parser before | Parser after | Symbols before | After | Files without symbols after |
| :--- | :--- | :--- | ---: | ---: | :--- |
| TypeScript/JavaScript | fallback 37 | tree-sitter 37 | 54 | 194 | 0 (was 16) |
| Go | fallback 5 | tree-sitter 5 | 191 | 195 | 0 |
| Rust | fallback 37 | tree-sitter 37 | 763 | 1,552 | 1 re-export file (was 10) |
| Java | fallback 85 | tree-sitter 85 | 1,649 | 1,077 | 5 `package-info.java` (was 8) |
| Terraform | fallback 5 | tree-sitter 5 | 439 | 457 | 0 (was 1) |

Java's count fell because the regex over-counted: in `Gson.java` it reported 80 methods, where
tree-sitter finds 38 methods and 2 constructors. Repository maps grew with the parsers: 102 to 126
files for TypeScript/JavaScript, and 41 to 64 for Terraform.
