# Tasks

## 1. Token Bounding and Safe Limits

- [ ] Write failing test for dense punctuation staying under the maximum token limit (`uv run devops ci test tests/test_rag_chunker.py -k test_dense_punctuation`).
- [ ] Implement `count_chunk_tokens` and token-bounded window splitting in `src/devops_cli/ai/rag/chunker.py` and delete duplicate `estimate_tokens` (`uv run devops ci test tests/test_rag_chunker.py`).
- [ ] Regenerate documentation and check consistency (`uv run devops docs generate --sync-readme`).

## 2. Polyglot Code, YAML, and Markdown Chunking

- [ ] Write failing tests for tree-sitter symbols, markdown fences, YAML nested names, and property tests (`uv run devops ci test tests/test_rag_polyglot_chunker.py`).
- [ ] Implement tree-sitter symbol chunking, `yaml.compose_all`, and `MarkdownIt` heading parsing, and delete regex patterns and wrappers (`uv run devops ci test tests/test_rag_polyglot_chunker.py`).
- [ ] Update `DocsIngester` to use shared `parse_markdown_headings` (`uv run devops ci test tests/test_docs_ingester.py`).
- [ ] Regenerate documentation and check consistency (`uv run devops docs generate --sync-readme`).

## 3. Verification and Clean Gate

- [ ] Run Hypothesis property tests and verify all tests execute in under 1 second (`uv run devops ci test tests/test_rag_chunker.py tests/test_rag_polyglot_chunker.py`).
- [ ] Verify regex patterns and wrappers are completely removed (`rg -n '_LANGUAGE_PATTERNS|_C_LIKE_PATTERN|_chunk_by_regex_symbols' src`).
- [ ] Run full CI checks (`uv run devops ci`).

## Workflow follow-up

- Pending a person: after `devops ai rag index --force`, `devops ai rag query` for a Rust `impl` method and a TypeScript class method returns the method chunk.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
