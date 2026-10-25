# Design

## Context

The RAG chunker split code on regular expressions and line prefixes.
This missed indented methods, split signatures, and matched lines in comments.
Also, chunk sizing used a fixed ratio of four characters per token.
Dense punctuation could exceed the context window of the embedding model.

## Decisions

### 1. Token Counting and Safe Bound

- Use `tiktoken` to count tokens for OpenAI embedding models and compatible subword encodings.
- Fall back to a documented safe bound of one token per character for worst-case punctuation when a tokenizer is unavailable.
- In `_split_window_by_token_limit`, measure token counts directly instead of using `max_chars = max_tokens * 4`.
- *Rejected alternative:* Keep four characters per token with a smaller character cap.
  *Evidence:* Text with dense punctuation still produces one token per character in Byte-Pair Encoding. Any multiple of characters per token fails on punctuation sequences.

### 2. Polyglot Symbol Extraction via `ai/ast`

- Use `TreeSitterEngine.parse_code` from `src/devops_cli/ai/ast/engine.py` to extract `PolyglotSymbol` spans.
- Create a chunk for each symbol span, retaining parent scope prefixes for methods.
- Languages without a tree-sitter grammar fall back to sliding line windows.
- Python retains its AST path.
- *Rejected alternative:* Extend regexes to recognize indentation.
  *Evidence:* Regexes cannot track multi-line parameter lists, nested blocks, or string literals accurately.

### 3. YAML and Markdown Parsers

- Use `yaml.compose_all` with `SafeLoader` to parse multi-document YAML files into document chunks.
- Extract document start and end lines from YAML node marks.
- Read symbols only from top-level `kind` and `metadata.name` mapping keys.
- Use `MarkdownIt("commonmark").parse` to extract heading tokens and their `map` line numbers.
- Ignore lines inside fenced code blocks.
- Export `parse_markdown_headings` for reuse in `DocsIngester`.
- *Rejected alternative:* Custom state machines for YAML separators and Markdown fences.
  *Evidence:* PyYAML and markdown-it-py are already pinned dependencies and handle edge cases reliably.
