# Design

## Context

See `proposal.md` - Why. The current codebase lacks detection for Unicode tag ASCII smuggling, zero-width steganography, and chat template delimiter mimicry. External tools (`llm-guard`, `rebuff`) are heavy or unmaintained.

## Goals / Non-Goals

**Goals:**
- Provide a pure-function detector in `src/devops_cli/security/prompt_injection.py` covering INJ001, INJ002, INJ003, INJ005, and EGR005.
- Provide a CLI subcommand `devops scan injection <target>` supporting `--sarif`, `--suppress`, `--show-suppressed`, `--fail-on`, `--min-severity`, `--format`, `--json`, and `--dry-run`.
- Expose `scan_injection` FastMCP tool through `CONST_MCP_EXPOSURE_TABLE`.
- Enforce Ruff rules `PLE2502`, `PLE2510`, `PLE2512`–`PLE2515` in `pyproject.toml`.

**Non-Goals:**
- INJ004 (adversarial instruction overrides) which flags legitimate security test phrases.
- EGR001–EGR004 which duplicate Gitleaks and existing secret redaction.
- Destructive stripping of zero-width joiners (U+200C/U+200D are load-bearing in international text).

## Decisions

### Decision 1: Pure-function module integrating directly with pipeline report
- **Rationale**: External scanners execute subprocesses, whereas prompt-injection detection evaluates strings and AST literals directly in Python memory. `devops scan injection` invokes `build_report` directly, bypassing the subprocess-only scanner registry.
- **Alternatives rejected**: Modifying `_create_default_scanners` in `security/registry.py`. Rejected because registry assumes subprocess commands.

### Decision 2: Delimiter escaping rather than deletion
- **Rationale**: Deleting chat template delimiters alters file contents and breaks formatting. Escaping preserves content while preventing prompt boundary breakout.
- **Alternatives rejected**: Stripping delimiters. Rejected because stripping alters user text irreversibly.

### Decision 3: Standard library implementation with no ML dependencies
- **Rationale**: Using `unicodedata`, `re`, and `secrets` keeps performance within tens of milliseconds and adds zero package dependencies.
- **Alternatives rejected**: `llm-guard` (pulls PyTorch, transformers, Presidio) and `rebuff` (unmaintained since 2024).

## Risks / Trade-offs

- [Risk: False positives on fixtures containing delimiters or tags] → Mitigation: Support `--suppress` via `load_policy` and `SuppressionPolicy`.
- [Risk: Accidental disclosure of canary tokens in telemetry or error logs] → Mitigation: Audit exclusively for the canary marker, never log active tokens, and mask credentials.
