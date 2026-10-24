# Tasks

## 1. Syntax-aware secret masking core and token lookbehinds

- [x] 1.1 Add failing tests for syntax-aware secret masking (`cfg.db_password` in code vs data, `settings.Hunter22` in code vs data), enclosed bracket tokens (`<ghs_...>`, `<sk-...>`) and placeholder preservation (`<ghp_token>`), and verify with `uv run devops ci test tests/test_consolidation_security_sanitizer.py`.
- [x] 1.2 Implement syntax-aware masking in `src/devops_cli/security/sanitizer.py`, delete `CONST_CODE_EXEMPTION_RECEIVERS` from `src/devops_cli/config/constants.py` and `sanitizer.py`, remove `<` from lookbehinds in `_SECRET_PATTERNS`, and verify with `uv run devops ci test tests/test_consolidation_security_sanitizer.py` and `grep -rn CONST_CODE_EXEMPTION_RECEIVERS src tests`.
- [x] 1.3 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## 2. Review and analysis callers integration

- [x] 2.1 Add failing tests for file syntax detection and multi-file review masking across Python and env files without a model, and verify with `uv run devops ci test tests/test_review_syntax_masking.py`.
- [x] 2.2 Add `CODE_LANGUAGES`, `syntax_from_language`, and `detect_syntax` in `src/devops_cli/ai/analyze/scanner.py`, wire syntax into `src/devops_cli/review/analysis.py`, `src/devops_cli/ai/review/cited_code.py`, and `src/devops_cli/ai/analyze/outlines.py`, and verify with `uv run devops ci test tests/test_review_syntax_masking.py`.
- [x] 2.3 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
