# Design

## Context

`devops_cli.ai.analyze.scanner.detect_language` classifies source files for file analysis and review workflows. See `proposal.md` for motivation. Currently, the MIME detection branch strips `+` from MIME subtypes such as `text/x-c++src`, which reduces the identifier to `c` and misclassifies C++ source files. Furthermore, `.tpl` files default to `plaintext` because the scanner lacks awareness of Helm chart hierarchy.

## Goals / Non-Goals

**Goals:**
- Classify all C++ source and header extensions as `cpp`.
- Inspect `.h` content using existing C++ construct patterns.
- Identify `.tpl` files inside Helm charts beside `Chart.yaml` as `helm`.
- Ensure deterministic language resolution when host MIME databases are empty.
- Eliminate mislabelling errors in sample validation reports.

**Non-Goals:**
- Replace Tree-Sitter AST engine grammars or introduce AST parsing for Helm templates.
- Support non-Helm template engines (.tpl files outside Helm charts remain plaintext).

## Decisions

### 1. Direct extension matching for C++ before MIME guessing
We check C++ extensions (`.cc`, `.cpp`, `.cxx`, `.c++`, `.hh`, `.hpp`, `.hxx`) directly before querying `mimetypes.guess_type()`.
- **Rejected alternative: Relying on MIME subtype parsing with regex adjustment.** Rejected because host MIME databases vary across operating systems, and minimal containers lack MIME entries completely.
- **Rejected alternative: Using Pygments lexers.** Rejected because Pygments classifies `.tpl` as Smarty, and filename lexer initialization adds unnecessary latency during bulk repository scans.

### 2. Contextual directory traversal for Helm templates
When inspecting a `.tpl` file, the scanner checks its parent directories for `Chart.yaml` or `chart.yaml`. If present, the language is `helm`; otherwise it defaults to `plaintext`.
- **Rejected alternative: Content-only template matching.** Rejected because Go templates, Hugo templates, and Jinja2 templates use identical `{{ ... }}` syntax. The presence of `Chart.yaml` defines a Helm chart boundary.

### 3. Shared C++ header content inspection
Reuse `_CPP_HEADER` construct detection to distinguish C++ headers from C headers when content is available.

## Risks / Trade-offs

- [Risk] Scanning deep directory hierarchies for `Chart.yaml` could impact performance.
  → Mitigation: Limit directory traversal to 5 parent levels, stopping at the repository or filesystem boundary.
