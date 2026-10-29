# Tasks

## 1. Ruff caps nesting at 4 blocks

- [x] Add failing checks to `tests/test_ruff_complexity_cap.py`: `PLR1702` enabled, `max_nested_blocks = 4`, lint preview with explicit preview rules, formatter preview off, five weakened tables named, and a negative control where five nested `if` blocks fail and four pass
  - Verification: `uv run devops ci test tests/test_ruff_complexity_cap.py`
- [x] Split the 12 functions with five nested blocks, each with one helper and the same behavior
  - Verification: `uv run ruff check --config pyproject.toml .`
- [x] Select `PLR1702` at 4 with lint preview and `explicit-preview-rules` in `pyproject.toml`
  - Verification: `uv run devops ci test tests/test_ruff_complexity_cap.py`

## 2. The hook and the nesting figure are deleted

- [ ] Add failing tests: the complexity scan gives no nesting finding and refuses `--max-indent`; the spec verifier records no indentation rule
  - Verification: `uv run devops ci test tests/test_scan_complexity.py tests/test_ai_spec.py tests/test_docs_command_resolver.py`
- [ ] Delete the `structural-invariants` hook, the nesting leg of the whole-tree test, the nesting code of `core/code_metrics.py`, `DEFAULT_MAX_NESTING_DEPTH`, `--max-indent` and the `max_indentation` rule, with their tests
  - Verification: `uv run devops ci test tests/test_code_metrics.py tests/test_architectural_invariants.py tests/test_review_ruff_mypy_evidence.py tests/test_mcp.py tests/test_fastmcp_contracts.py`
- [ ] Name `PLR1702` at 4 in `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/SELF_IMPROVEMENT.md`, `docs/VISION.md` and the code-review knowledge-base page, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 3. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1876-ruff-nesting-cap`

## Workflow follow-up

- #2600 decides whether `devops scan complexity` and the inspection hotspots read Ruff's `C901` count in place of the McCabe port.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
