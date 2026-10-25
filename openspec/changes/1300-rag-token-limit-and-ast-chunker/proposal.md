# Proposal

## Why

Issue #1300: RAG chunks are bounded at 8,192 estimated tokens with four characters per token.
Text with dense punctuation or short identifiers can exceed the real token limit of the embedding model.
Indexing then fails with an error from the embedding model.
Also, the RAG chunker splits code, YAML, and Markdown with line-anchored regexes and line prefixes.
The regexes miss indented definitions such as a Rust function in an implementation block or a TypeScript method.
The regexes also match symbol patterns inside comments and strings.

## What Changes

- Delete the duplicate `estimate_tokens` function from `src/devops_cli/ai/rag/chunker.py`.
- Measure chunk token counts with a tokenizer that matches the configured embedding model or a safe bound.
- Bound window slices and sub-windows with actual token counts so dense punctuation stays under 8,192 tokens.
- Replace regex tables and per-language wrappers with `TreeSitterEngine.parse_code` symbol spans from `ai/ast`.
- Replace line-prefix YAML parsing with `yaml.compose_all` and SafeLoader to extract document marks and top-level symbols.
- Replace regex heading detection with `MarkdownIt("commonmark").parse` heading token line maps.
- Export `parse_markdown_headings` so that `DocsIngester` shares the parser.
- This change alters no CLI commands, options, messages, manifests, or service behavior.
- The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/rag/chunker.py`: Delete regex tables, duplicate `estimate_tokens`, and wrappers. Use `TreeSitterEngine`, `yaml.compose_all`, and `MarkdownIt`.
- `src/devops_cli/ai/library/docs_ingester.py`: Use `parse_markdown_headings` to avoid heading detection inside code fences.
- `tests/test_rag_chunker.py`: Add tests for dense punctuation, markdown fences, YAML nested names, and Hypothesis properties.
- `tests/test_rag_polyglot_chunker.py`: Add table tests for indented methods, multi-line signatures, and comments.

## Feasibility

- Confirmed `TreeSitterEngine` in `src/devops_cli/ai/ast/engine.py` supports Rust, TypeScript, Go, Java, C#, C, C++, and HCL.
- Confirmed `TreeSitterEngine.parse_code` returns exact `PolyglotSymbol` line spans and ignores comments.
- Confirmed `PyYAML` `yaml.compose_all` with `SafeLoader` returns document node marks and top-level mapping keys.
- Confirmed `markdown-it-py` CommonMark parser returns heading tokens with line ranges and ignores code fences.
- Confirmed `tiktoken` encodes punctuation accurately and provides safe subword token bounds.

## Existing Tool Considered

We use the existing open libraries in `pyproject.toml`:
- `tiktoken` for exact token counting.
- `tree-sitter` and language grammars through `ai/ast` for polyglot symbols.
- `PyYAML` (`yaml.compose_all`, `SafeLoader`) for YAML documents.
- `markdown-it-py` for CommonMark headings.
- `hypothesis` for property-based testing.

The change deletes internal hand-rolled code:
- `_LANGUAGE_PATTERNS`
- `_C_LIKE_PATTERN`
- `_chunk_by_regex_symbols`
- `_chunk_language_symbols`
- `_chunk_go`
- `_chunk_rust`
- `_chunk_js_ts`
- `_chunk_c_like`
- `_chunk_terraform`
- `_chunk_sql`
- duplicate `estimate_tokens` in `src/devops_cli/ai/rag/chunker.py`
