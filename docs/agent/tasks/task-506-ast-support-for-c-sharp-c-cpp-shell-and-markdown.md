# Task 506: AST Support for C#, C/C++, Shell and Markdown

**Issue**: [#506](https://github.com/dan-petty/devops-cli/issues/506)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

The AST engine mapped Python, TypeScript, JavaScript, Go, Rust, Java and HCL. C#, C, C++, shell
and Markdown files yielded no symbols, so repomaps, context packing and review grounding saw
nothing in them.

### Key Deliverables Completed:

- [x] **Grammars**, from the tree-sitter and tree-sitter-grammars organisations:
  - `tree-sitter-c-sharp` 0.23.5
  - `tree-sitter-c` 0.24.2
  - `tree-sitter-cpp` 0.23.4 (the official grammar; its last release was November 2024)
  - `tree-sitter-bash` 0.25.1
  - `tree-sitter-markdown` 0.5.1, block grammar

  Extensions: `.cs`, `.c`, `.h`, `.cc`/`.cpp`/`.cxx`/`.c++`/`.hh`/`.hpp`/`.hxx`, `.sh`/`.bash`/`.envsh` (the nginx image's entrypoint scripts),
  `.md`/`.markdown`. The names `shell`, `sh`, `c#`, `cs`, `c++` and `md` are aliases.
- [x] **Headers**: a `.h` header is C++ when it has a namespace, a template, a class with a
  body or `::`, and C otherwise. fmt's headers are C++.
- [x] **C and C++**:
  - functions are named through their declarator chain (`*name`, `name(args)`, `Class::name`,
    `operator++`, `~T`);
  - a definition in a class body, or one with a qualified name, is a method;
  - prototypes at file scope count, through include guards, `extern "C"`, namespaces and
    templates, so a header's API is listed;
  - structs, classes, unions and enums count where defined, not where merely named;
  - typedefs, `using` aliases, namespaces and function-like macros also count.
- [x] **C#**: namespaces (block and file-scoped), classes, records, structs, interfaces, enums,
  delegates, methods and constructors.
- [x] **Shell**: `name() {}` and `function name {}`.
- [x] **Markdown**: ATX and setext headings, as a new `heading` kind, with closing hashes
  dropped. Front matter and `#` comments in fenced code are skipped.
- [x] **Fallback extractors**, used without a grammar:
  - line patterns for C#, C, C++ and shell functions and types, skipping control statements and
    calls;
  - Markdown ATX headings outside front matter and fenced code.
- [x] **Checked on the pinned samples**:

  | Sample | Files | Files with symbols | Symbols |
  |---|---|---|---|
  | serilog | 216 | 209 | 1,997 |
  | cJSON | 99 | 97 | 2,034 (1,988 functions, incl. every `CJSON_PUBLIC` prototype) |
  | fmt | 74 | 70 | 7,279 (71 files as C++) |
  | nvm | 6 | 6 | 170 functions |
  | kind docs | 47 | 33 | 274 headings |

  The files without symbols declare none. For example, 14 kind docs pages have front matter
  and prose only.
- [x] **Automated Tests & Quality Gates** (`tests/test_ast_more_languages.py`), with snippets
  following each sample, covering:
  - each language's symbols and scopes;
  - C export macros, guards and linkage;
  - C++ members and qualified definitions;
  - Markdown front matter and fences;
  - extensions;
  - header detection;
  - every fallback;
  - aliases.

  Shell outlines now report `bash`. 100% passing status across Gated CI validation suite
  (`uv run devops ci`).
