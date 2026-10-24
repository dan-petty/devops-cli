# Proposal

## Why

Issue #889 shows that `mask_secrets` distinguishes code expressions from credential literals using an arbitrary receiver allowlist (`CONST_CODE_EXEMPTION_RECEIVERS`). This causes false redactions in valid code expressions (`password=cfg.db_password`) and leaks secrets in configuration files (`password=settings.Hunter22` in an env file). In addition, token patterns containing `<` in lookbehinds fail to mask tokens in bracketed contexts (`<ghs_...>`).

## What Changes

This change replaces receiver-name filtering with syntax-aware secret masking:
- `mask_secrets` accepts a `syntax` parameter (`code` vs `data`, defaulting to `data`).
- In `code` syntax, unquoted right-hand side expressions consisting of names, calls, or indexing are preserved as code. In `data` syntax, credential assignments are unconditionally masked.
- `ai.analyze.scanner` defines programming language classification (`syntax_from_language`, `detect_syntax`) mapping scanner languages to `code` or `data`.
- Review callers (`review.analysis`, `ai.review.cited_code`, `ai.analyze.outlines`) detect and pass file syntax per reviewed file.
- Delete `CONST_CODE_EXEMPTION_RECEIVERS` from constants and sanitizer logic.
- Drop `<` from lookbehinds for GitHub tokens and OpenAI / Anthropic key patterns while preserving length bounds, ensuring tokens in brackets are masked while placeholders remain intact.

This change fits one pull request.

## Capabilities

### New Capabilities
- `secret-masking`: Mask credentials and secret patterns in source code excerpts, logs, and telemetry based on file syntax.

### Modified Capabilities
None.

## Impact

- Security sanitizer: Updates `mask_secrets`, `redact_text`, and `mask_dict_secrets` signatures and literal masking logic.
- Config constants: Deletes `CONST_CODE_EXEMPTION_RECEIVERS`.
- File analysis: Adds syntax detection helpers in `devops_cli.ai.analyze.scanner`.
- Review pipeline & analysis: Single-file review callers pass file syntax into `mask_secrets`.

## Feasibility

I confirmed the premise against the real system:
- Verified `mask_secrets("password=cfg.db_password")` currently masks `password=<masked-password>` because `cfg` is not in `CONST_CODE_EXEMPTION_RECEIVERS`.
- Verified `mask_secrets("password=settings.Hunter22")` currently fails to mask `settings.Hunter22` because `settings` is in `CONST_CODE_EXEMPTION_RECEIVERS`.
- Verified `<ghs_...>` installation tokens are unmasked due to `(?<![A-Za-z0-9_<])` lookbehinds in `_SECRET_PATTERNS`.
- Verified `detect_language` in `ai/analyze/scanner.py` reliably identifies `.py` as `python` and `.env` as `env`.

## Existing Tool Considered

Libraries such as TruffleHog and detect-secrets do not support context-sensitive in-flight redaction for AST / LLM prompt construction with syntax distinction between programming languages and configuration files. Building syntax-aware masking internally requires approximately 80 lines of code, 3,500 tokens of agent context, and 15 minutes of elapsed time. This change deletes `CONST_CODE_EXEMPTION_RECEIVERS` and eliminates arbitrary identifier lists.
