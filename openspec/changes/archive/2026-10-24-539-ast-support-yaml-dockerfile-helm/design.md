# Design

## Context

`TreeSitterEngine` currently provides multilingual AST symbol extraction for thirteen languages. It lacks support for YAML, Dockerfiles, and Helm templates. This leaves Kubernetes manifests and Dockerfiles without symbols in repository maps and sample validations. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Parse Dockerfiles with `tree-sitter-dockerfile` and extract stage aliases and FROM images.
- Parse YAML files with `tree-sitter-yaml` and extract Kubernetes resource kind and name pairs or top-level keys.
- Parse Helm `.tpl` templates with a balanced block parser and extract named template definitions.
- Update `TreeSitterEngine`, language detection, and repository file discovery.

**Non-Goals:**
- Full semantic validation of Kubernetes schema properties.
- Evaluating Go template expressions inside Helm charts at AST parse time.
- Modifying `scanner.py` file analysis classification (tracked in issue #540).

## Decisions

- **Use `tree-sitter-yaml` and `tree-sitter-dockerfile` for AST parsing**:
  - Integrate official tree-sitter packages pinned in `pyproject.toml`.
  - *Rejected alternative*: Using PyYAML for AST parsing.
  - *Evidence for rejection*: PyYAML does not provide line and column span positions and crashes on Helm-templated YAML files.
  - *Rejected alternative*: Regex parsing for Dockerfiles.
  - *Evidence for rejection*: Dockerfiles support multi-line instructions, build options, flags, and platform parameters that tree-sitter parses accurately.

- **Clean Helm directives before YAML parsing**:
  - Mask standalone Go template directive lines (`{{ ... }}`) as comments before invoking `tree-sitter-yaml`.
  - *Rejected alternative*: Parsing raw Helm-templated YAML directly without masking.
  - *Evidence for rejection*: Standalone `{{- if ... }}` directives at file start cause tree-sitter to fail parsing mapping pairs across the entire file.

- **Balanced block parser for Helm templates**:
  - Use a stack-based block counter tracking `define`, `if`, `with`, `range`, and `end` tags to locate named templates and their exact spans.
  - *Rejected alternative*: Adding a third-party Go template parser package.
  - *Evidence for rejection*: PyPI contains no maintained tree-sitter or AST package for Go/Helm templates.

## Risks / Trade-offs

- [Syntax errors in complex Helm templates] → Tree-sitter error recovery preserves valid surrounding mapping pairs.
- [Oversized YAML files] → Existing `DEFAULT_MAX_AST_FILE_SIZE_BYTES` guards prevent reading or parsing files over the size threshold.
