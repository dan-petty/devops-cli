# Design

## Context

See `proposal.md` for background and rationale. Secret masking runs on source excerpts sent to model providers, error logs, and telemetry payloads. Currently, `CONST_CODE_EXEMPTION_RECEIVERS` checks 14 hardcoded identifiers on the LHS of dotted expressions, leading to incorrect masking in code and secret leakage in config.

## Goals / Non-Goals

**Goals:**
- Provide syntax-aware masking in `mask_secrets` via `syntax: Literal["code", "data"] = "data"`.
- In `code` syntax, preserve unquoted expressions composed of names, calls, or indexing.
- In `data` syntax, mask all assigned credential values.
- Completely remove `CONST_CODE_EXEMPTION_RECEIVERS`.
- Drop `<` from lookbehinds for GitHub and LLM token regexes.
- Update review and analysis single-file callers to pass the detected file syntax.

**Non-Goals:**
- Do not retain backward compatibility shims or keep `CONST_CODE_EXEMPTION_RECEIVERS`.
- Do not modify URL credential masking rules.
- Do not parse full ASTs during masking; regex with syntactic expression structure checks maintains high throughput.

## Decisions

### 1. Syntax parameter on `mask_secrets` defaulting to `data`
`mask_secrets` and `redact_text` take `syntax: Literal["code", "data"] = "data"`.
- *Rationale*: Callers handling error messages, logs, telemetry, and unclassified files default to `data`, guaranteeing aggressive secret masking without leakage.
- *Rejected Alternative*: Heuristic content sniffing inside `mask_secrets`. Rejected because detecting code vs data from arbitrary text snippets is unreliable and creates circular dependencies between `security` and `ai`.

### 2. Closed language set in `ai.analyze.scanner`
`ai.analyze.scanner` defines `CODE_LANGUAGES`, `syntax_from_language`, and `detect_syntax`.
- *Rationale*: The scanner owns the project's language taxonomy (`_EXT_LANG_FALLBACK`, `_MANIFEST_LANG_MAP`). Review callers import syntax detection from `scanner` and pass the resulting syntax to `mask_secrets`.
- *Rejected Alternative*: Defining language taxonomy in `devops_cli.security.sanitizer`. Rejected because `security` is a low-level foundation layer that should not duplicate scanner file classifications.

### 3. Pre-compiled pattern tables for syntax modes
`sanitizer.py` pre-compiles `_SECRET_PATTERNS_CODE` and `_SECRET_PATTERNS_DATA` (or parameterizes literal maskers) at module import time.
- *Rationale*: Pre-compiling static patterns avoids dynamic regex re-compilation or per-call function instantiation in high-volume masking loops.
- *Rejected Alternative*: Inspecting call stack or dynamic global state. Rejected because global state is thread-unsafe and violates hermetic execution.

### 4. Remove `<` from lookbehinds
Drop `<` from `(?<![A-Za-z0-9_<])` and `(?<![a-zA-Z0-9/\\<])`.
- *Rationale*: Tokens enclosed in angle brackets (`<ghs_...>`) must be masked. Existing length quantifiers (`{10,}`, `{36,}`, `{19,}`) ensure placeholders like `<ghp_token>` remain intact.
- *Rejected Alternative*: Adding separate regexes for bracketed tokens. Rejected because removing `<` from the negative lookbehind addresses the root cause directly without regex duplication.

## Risks / Trade-offs

- [Risk] Unquoted identifier in code syntax could be a hardcoded credential. → Mitigation: Hardcoded credentials in source code are typically string literals (quoted) or numeric, which are masked. Unquoted identifiers represent variables, constants, or attributes that reviewers need to inspect.
- [Risk] Review callers failing to pass syntax. → Mitigation: Default `data` syntax masks strictly, ensuring no sensitive data leaks if a caller omits the argument.
